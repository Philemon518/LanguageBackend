"""Mastery tracking and spaced review."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.orm import CurriculumVersion, ExerciseAttempt, Lesson, ObjectiveMastery, Unit

SKILL_WEIGHTS = {
    "listening": 1.0,
    "speaking": 0.9,
    "reading": 0.7,
    "writing": 0.6,
}


def compute_mastery_delta(skill: str, score: float, correct: bool) -> float:
    base = 0.15 if correct else -0.05
    weight = SKILL_WEIGHTS.get(skill, 0.5)
    return round(base * max(score, 0.01 if not correct else score) * weight, 3)


def review_interval_days(mastery: float) -> int:
    if mastery < 0.3:
        return 1
    if mastery < 0.6:
        return 3
    if mastery < 0.8:
        return 7
    return 14


async def update_mastery(
    db: AsyncSession,
    user_id: UUID,
    objective_id: str,
    skill: str,
    delta: float,
) -> dict[str, float]:
    result = await db.execute(
        select(ObjectiveMastery).where(
            ObjectiveMastery.user_id == user_id,
            ObjectiveMastery.objective_id == objective_id,
            ObjectiveMastery.skill == skill,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = ObjectiveMastery(
            user_id=user_id,
            objective_id=objective_id,
            skill=skill,
            mastery=max(0.0, min(1.0, 0.1 + delta)),
        )
        db.add(row)
    else:
        row.mastery = max(0.0, min(1.0, row.mastery + delta))
    row.review_due_at = datetime.now(UTC) + timedelta(
        days=review_interval_days(row.mastery)
    )
    return {skill: row.mastery}


async def get_review_queue(db: AsyncSession, user_id: UUID) -> list[str]:
    now = datetime.now(UTC)
    result = await db.execute(
        select(ObjectiveMastery).where(
            ObjectiveMastery.user_id == user_id,
            ObjectiveMastery.review_due_at <= now,
        )
    )
    return [m.objective_id for m in result.scalars().all()]


async def get_user_mastery(db: AsyncSession, user_id: UUID) -> list[dict]:
    result = await db.execute(
        select(ObjectiveMastery).where(ObjectiveMastery.user_id == user_id)
    )
    return [
        {
            "objective_id": m.objective_id,
            "skill": m.skill,
            "mastery": m.mastery,
            "review_due_at": m.review_due_at.isoformat() if m.review_due_at else None,
        }
        for m in result.scalars().all()
    ]


async def count_completed_lessons(db: AsyncSession, user_id: UUID) -> int:
    from ..models.orm import LessonProgress

    result = await db.execute(
        select(LessonProgress).where(
            LessonProgress.user_id == user_id, LessonProgress.completed.is_(True)
        )
    )
    return len(result.scalars().all())


async def has_correct_completion(
    db: AsyncSession, user_id: UUID, lesson_id: str, exercise_id: str
) -> bool:
    result = await db.execute(
        select(ExerciseAttempt.id).where(
            ExerciseAttempt.user_id == user_id,
            ExerciseAttempt.lesson_id == lesson_id,
            ExerciseAttempt.exercise_id == exercise_id,
            ExerciseAttempt.correct.is_(True),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def get_skill_summary(db: AsyncSession, user_id: UUID) -> list[dict]:
    skills = ("listening", "speaking", "reading", "writing")
    totals = {skill: 0 for skill in skills}
    completed = {skill: 0 for skill in skills}
    exercise_skills: dict[tuple[str, str], str] = {}

    version_result = await db.execute(
        select(CurriculumVersion)
        .where(CurriculumVersion.level == "beginner")
        .order_by(CurriculumVersion.created_at.desc())
        .limit(1)
    )
    version = version_result.scalar_one_or_none()
    lesson_result = await db.execute(
        select(Lesson).join(Unit, Lesson.unit_id == Unit.id).where(
            Unit.curriculum_version_id == version.id
        )
        if version
        else select(Lesson).where(False)
    )
    for lesson in lesson_result.scalars().all():
        for step in (lesson.content_json or {}).get("steps", []):
            skill = step.get("skill")
            if skill in totals:
                totals[skill] += 1
                exercise_skills[(lesson.id, step.get("id", ""))] = skill

    attempts_result = await db.execute(
        select(
            ExerciseAttempt.lesson_id,
            ExerciseAttempt.exercise_id,
            ExerciseAttempt.skill,
        ).where(
            ExerciseAttempt.user_id == user_id,
            ExerciseAttempt.correct.is_(True),
        )
    )
    seen: set[tuple[str, str]] = set()
    for lesson_id, exercise_id, _recorded_skill in attempts_result.all():
        key = (lesson_id, exercise_id)
        skill = exercise_skills.get(key)
        if key not in seen and skill in completed:
            seen.add(key)
            completed[skill] += 1

    return [
        {
            "skill": skill,
            "completed": completed[skill],
            "total": totals[skill],
            "percentage": round(
                completed[skill] / totals[skill] * 100, 1
            )
            if totals[skill]
            else 0.0,
        }
        for skill in skills
    ]


async def record_attempt(
    db: AsyncSession,
    user_id: UUID,
    lesson_id: str,
    exercise_id: str,
    skill: str,
    response: dict,
    correct: bool,
    score: float,
    feedback: str | None,
    idempotency_key: str | None,
) -> ExerciseAttempt:
    if idempotency_key:
        existing = await db.execute(
            select(ExerciseAttempt).where(
                ExerciseAttempt.user_id == user_id,
                ExerciseAttempt.idempotency_key == idempotency_key,
            )
        )
        found = existing.scalar_one_or_none()
        if found:
            return found

    attempt = ExerciseAttempt(
        user_id=user_id,
        lesson_id=lesson_id,
        exercise_id=exercise_id,
        skill=skill,
        response_json=response,
        correct=correct,
        score=score,
        feedback=feedback,
        idempotency_key=idempotency_key,
    )
    db.add(attempt)
    return attempt
