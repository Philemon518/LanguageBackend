"""Attempts and progress endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import AuthUser, get_current_user
from ..core.database import get_db
from ..models.orm import ExerciseAttempt, LessonProgress, UserProfile
from ..models.schemas import (
    AttemptRequest,
    AttemptResponse,
    PracticeNextResponse,
    ProgressResponse,
    SkillSummaryResponse,
    WritingFeedback,
)
from ..services.curriculum import get_lesson
from ..services.grading import grade_exercise, grade_writing
from ..services.mastery import (
    compute_mastery_delta,
    count_completed_lessons,
    get_review_queue,
    get_skill_summary,
    get_user_mastery,
    has_correct_completion,
    record_attempt,
    update_mastery,
)

router = APIRouter(tags=["learning"])


@router.post("/attempts", response_model=AttemptResponse)
async def submit_attempt(
    body: AttemptRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lesson = await get_lesson(db, body.lesson_id)
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    step = next((s for s in lesson.steps if s.id == body.exercise_id), None)
    if not step:
        raise HTTPException(404, "Exercise not found")

    skill = step.skill
    already_completed = await has_correct_completion(
        db, user.id, body.lesson_id, body.exercise_id
    )
    correct, score, feedback = grade_exercise(step, body.response)
    skill_point_awarded = correct and not already_completed
    delta_val = compute_mastery_delta(skill, score, correct)
    objective_id = step.metadata.get("objective_id", body.exercise_id)
    mastery_delta = await update_mastery(db, user.id, objective_id, skill, delta_val)

    attempt = await record_attempt(
        db,
        user.id,
        body.lesson_id,
        body.exercise_id,
        skill,
        body.response,
        correct,
        score,
        feedback,
        body.idempotency_key,
    )
    await db.flush()

    # Update lesson progress
    prog_result = await db.execute(
        select(LessonProgress).where(
            LessonProgress.user_id == user.id,
            LessonProgress.lesson_id == body.lesson_id,
        )
    )
    prog = prog_result.scalar_one_or_none()
    correct_result = await db.execute(
        select(ExerciseAttempt.exercise_id)
        .where(
            ExerciseAttempt.user_id == user.id,
            ExerciseAttempt.lesson_id == body.lesson_id,
            ExerciseAttempt.correct.is_(True),
        )
        .distinct()
    )
    correct_exercise_ids = set(correct_result.scalars().all())
    first_incomplete = next(
        (
            index
            for index, lesson_step in enumerate(lesson.steps)
            if lesson_step.id not in correct_exercise_ids
        ),
        len(lesson.steps),
    )
    if prog is None:
        prog = LessonProgress(
            user_id=user.id,
            lesson_id=body.lesson_id,
            current_step=first_incomplete,
            state_json={"last_exercise": body.exercise_id},
        )
        db.add(prog)
    else:
        prog.current_step = first_incomplete
        prog.state_json = {**prog.state_json, "last_exercise": body.exercise_id}
    prog.completed = first_incomplete >= len(lesson.steps)

    profile_result = await db.execute(select(UserProfile).where(UserProfile.id == user.id))
    profile = profile_result.scalar_one()
    if correct:
        profile.total_xp += int(score * 10)

    await db.commit()
    await db.refresh(attempt)

    return AttemptResponse(
        id=attempt.id,
        correct=correct,
        score=score,
        feedback=feedback,
        mastery_delta=mastery_delta,
        skill_point_awarded=skill_point_awarded,
    )


@router.get("/progress", response_model=ProgressResponse)
async def user_progress(
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    profile_result = await db.execute(select(UserProfile).where(UserProfile.id == user.id))
    profile = profile_result.scalar_one()
    mastery = await get_user_mastery(db, user.id)
    review = await get_review_queue(db, user.id)
    completed = await count_completed_lessons(db, user.id)
    return ProgressResponse(
        level=profile.current_level,
        streak_days=profile.streak_days,
        total_xp=profile.total_xp,
        lessons_completed=completed,
        mastery=mastery,
        review_queue=review,
    )


@router.get("/skills", response_model=SkillSummaryResponse)
async def skill_summary(
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return SkillSummaryResponse(skills=await get_skill_summary(db, user.id))


@router.get("/practice/next", response_model=PracticeNextResponse)
async def next_practice(
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    review = await get_review_queue(db, user.id)
    if review:
        return PracticeNextResponse(
            lesson_id="review",
            exercise_id=review[0],
            reason="spaced_review",
        )
    return PracticeNextResponse(
        lesson_id="sound-01-water",
        exercise_id="s1-hear",
        reason="continue_curriculum",
    )


@router.post("/writing/feedback", response_model=WritingFeedback)
async def writing_feedback(
    text: str,
    patterns: list[str],
    vocab: list[str],
    user: Annotated[AuthUser, Depends(get_current_user)],
):
    acceptable, _score, feedback = grade_writing(text, patterns, vocab)
    matched_vocab = [v for v in vocab if v in text]
    matched_patterns = [p for p in patterns if p.replace(" ", "") in text.replace(" ", "")]
    return WritingFeedback(
        acceptable=acceptable,
        feedback=feedback or "",
        matched_vocab=matched_vocab,
        matched_patterns=matched_patterns,
    )
