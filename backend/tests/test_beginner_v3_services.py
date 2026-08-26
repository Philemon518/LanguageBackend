"""Focused application-service coverage for beginner curriculum v3."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.learning import submit_attempt
from app.core.auth import AuthUser
from app.core.config import get_settings
from app.models.orm import (
    Base,
    CurriculumVersion,
    Lesson,
    LessonProgress,
    MediaAsset,
    ObjectiveMastery,
    Unit,
    UserProfile,
)
from app.models.schemas import AttemptRequest, ExerciseStep
from app.services.curriculum import get_lesson, list_road
from app.services.grading import grade_exercise
from app.services.mastery import count_completed_lessons, get_user_mastery


async def _database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _lesson(lesson_id: str, unit_id: str, steps: list[dict]) -> Lesson:
    return Lesson(
        id=lesson_id,
        unit_id=unit_id,
        title=lesson_id,
        lesson_type="sound",
        sort_order=1,
        objectives=[],
        content_json={
            "target": {
                "traditional": "水",
                "english": "water",
                "words": [{"traditional": "水"}],
            },
            "steps": steps,
        },
        status="published",
    )


@pytest.mark.asyncio
async def test_road_and_lesson_use_latest_version_and_resolve_nested_audio():
    engine, sessions = await _database()
    settings = get_settings()
    async with sessions() as db:
        v2 = CurriculumVersion(version="2.0.0", level="beginner", status="published")
        v3 = CurriculumVersion(version="3.0.0", level="beginner", status="published")
        db.add_all([v2, v3])
        await db.flush()
        db.add_all(
            [
                Unit(
                    id="v2-unit",
                    curriculum_version_id=v2.id,
                    title="Old",
                    phase="sound",
                    sort_order=1,
                    prerequisites=[],
                ),
                Unit(
                    id="v3-unit",
                    curriculum_version_id=v3.id,
                    title="New",
                    phase="sound",
                    sort_order=1,
                    prerequisites=[],
                ),
            ]
        )
        db.add(_lesson("v2-lesson", "v2-unit", []))
        db.add(
            _lesson(
                "v3-lesson",
                "v3-unit",
                [
                    {
                        "id": "compare",
                        "type": "audio_comparison",
                        "skill": "listening",
                        "prompt": "Compare",
                        "correct_option_id": "a",
                        "options": [
                            {
                                "id": "a",
                                "label": "A",
                                "comparison": {"samples": [{"audio": {"text": "嵌套測試"}}]},
                            }
                        ],
                    }
                ],
            )
        )
        asset = MediaAsset(
            content_hash="a" * 64,
            text="嵌套測試",
            voice=settings.cantonese_ai_voice_id,
            model=settings.cantonese_ai_tts_model,
            storage_path="beginner/water.wav",
            public_url="/media/beginner/water.wav",
        )
        db.add(asset)
        await db.commit()

        road = await list_road(db)
        lesson = await get_lesson(db, "v3-lesson")

        assert [item.id for item in road] == ["v3-lesson"]
        assert road[0].word_count == 1
        assert await get_lesson(db, "v2-lesson") is None
        nested_audio = lesson.steps[0].options[0].model_extra["comparison"]["samples"][0]["audio"]
        assert nested_audio["url"] == "/media/beginner/water.wav"
        assert nested_audio["asset_id"] == str(asset.id)
    await engine.dispose()


@pytest.mark.asyncio
async def test_lesson_intro_advances_without_xp_or_mastery():
    engine, sessions = await _database()
    user_id = uuid.uuid4()
    async with sessions() as db:
        version = CurriculumVersion(version="3.0.0", level="beginner", status="published")
        db.add(version)
        await db.flush()
        db.add(
            Unit(
                id="unit",
                curriculum_version_id=version.id,
                title="Unit",
                phase="sound",
                sort_order=1,
                prerequisites=[],
            )
        )
        db.add(
            _lesson(
                "intro-lesson",
                "unit",
                [{"id": "intro", "type": "lesson_intro", "metadata": {}}],
            )
        )
        db.add(
            UserProfile(
                id=user_id,
                username="intro-user",
                password_hash="unused",
                total_xp=0,
            )
        )
        await db.commit()

        response = await submit_attempt(
            AttemptRequest(
                lesson_id="intro-lesson",
                exercise_id="intro",
                skill="reading",
                response={},
            ),
            AuthUser(id=user_id, username="intro-user"),
            db,
        )

        progress = (
            await db.execute(select(LessonProgress).where(LessonProgress.user_id == user_id))
        ).scalar_one()
        profile = await db.get(UserProfile, user_id)
        mastery = (
            (await db.execute(select(ObjectiveMastery).where(ObjectiveMastery.user_id == user_id)))
            .scalars()
            .all()
        )

        assert response.correct
        assert response.mastery_delta == {}
        assert not response.skill_point_awarded
        assert progress.current_step == 1
        assert progress.completed
        assert profile.total_xp == 0
        assert mastery == []
    await engine.dispose()


def test_v3_choice_comparison_and_typing_types_are_graded():
    for exercise_type in ("choice", "image_comparison", "audio_comparison"):
        step = ExerciseStep(
            id=exercise_type,
            type=exercise_type,
            skill="reading",
            prompt="Choose",
            correct_option_id="right",
        )
        assert grade_exercise(step, {"selected_option_id": "right"})[:2] == (True, 1.0)

    typing = ExerciseStep(
        id="typing",
        type="typing",
        skill="writing",
        prompt="Type",
        metadata={"accepted_answers": ["水", "seoi2"]},
    )
    assert grade_exercise(typing, {"text": "水"})[:2] == (True, 1.0)


@pytest.mark.asyncio
async def test_progress_and_mastery_ignore_older_beginner_versions():
    engine, sessions = await _database()
    user_id = uuid.uuid4()
    async with sessions() as db:
        v2 = CurriculumVersion(version="2.0.0", level="beginner", status="published")
        v3 = CurriculumVersion(version="3.0.0", level="beginner", status="published")
        db.add_all([v2, v3])
        await db.flush()
        db.add_all(
            [
                Unit(
                    id="old-unit",
                    curriculum_version_id=v2.id,
                    title="Old",
                    phase="sound",
                    sort_order=1,
                    prerequisites=[],
                ),
                Unit(
                    id="new-unit",
                    curriculum_version_id=v3.id,
                    title="New",
                    phase="sound",
                    sort_order=1,
                    prerequisites=[],
                ),
            ]
        )
        db.add(
            _lesson(
                "old-lesson",
                "old-unit",
                [
                    {
                        "id": "old-exercise",
                        "type": "choice",
                        "skill": "reading",
                        "metadata": {"objective_id": "old-objective"},
                    }
                ],
            )
        )
        db.add(
            _lesson(
                "new-lesson",
                "new-unit",
                [
                    {
                        "id": "new-exercise",
                        "type": "choice",
                        "skill": "reading",
                        "metadata": {"objective_id": "new-objective"},
                    }
                ],
            )
        )
        db.add_all(
            [
                LessonProgress(user_id=user_id, lesson_id="old-lesson", completed=True),
                ObjectiveMastery(
                    user_id=user_id,
                    objective_id="old-objective",
                    skill="reading",
                    mastery=1,
                ),
                ObjectiveMastery(
                    user_id=user_id,
                    objective_id="new-objective",
                    skill="reading",
                    mastery=0.5,
                ),
            ]
        )
        await db.commit()

        assert await count_completed_lessons(db, user_id) == 0
        mastery = await get_user_mastery(db, user_id)
        assert [item["objective_id"] for item in mastery] == ["new-objective"]
    await engine.dispose()
