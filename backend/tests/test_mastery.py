"""Test mastery calculations."""

import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.orm import Base, CurriculumVersion, ExerciseAttempt, Lesson, Unit
from app.services.mastery import (
    compute_mastery_delta,
    get_skill_summary,
    review_interval_days,
)


def test_mastery_delta_positive():
    delta = compute_mastery_delta("listening", 1.0, True)
    assert delta > 0


def test_mastery_delta_negative():
    delta = compute_mastery_delta("listening", 0.0, False)
    assert delta < 0


def test_review_intervals():
    assert review_interval_days(0.2) == 1
    assert review_interval_days(0.9) == 14


@pytest.mark.asyncio
async def test_skill_summary_counts_first_correct_completion_once():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid.uuid4()

    async with sessions() as db:
        version = CurriculumVersion(
            version="2.0.0", level="beginner", status="published"
        )
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
            Lesson(
                id="lesson",
                unit_id="unit",
                title="Lesson",
                lesson_type="sound",
                sort_order=1,
                objectives=[],
                content_json={
                    "steps": [
                        {"id": "listen", "skill": "listening"},
                        {"id": "speak", "skill": "speaking"},
                        {"id": "read", "skill": "reading"},
                        {"id": "write", "skill": "writing"},
                    ]
                },
                status="published",
            )
        )
        for _ in range(2):
            db.add(
                ExerciseAttempt(
                    user_id=user_id,
                    lesson_id="lesson",
                    exercise_id="listen",
                    skill="listening",
                    response_json={},
                    correct=True,
                    score=1,
                )
            )
        await db.commit()

        summary = await get_skill_summary(db, user_id)
        listening = next(item for item in summary if item["skill"] == "listening")
        assert listening == {
            "skill": "listening",
            "completed": 1,
            "total": 1,
            "percentage": 100.0,
        }
        assert all(item["total"] == 1 for item in summary)
    await engine.dispose()
