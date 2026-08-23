"""Tests for curriculum road filtering."""

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import app.core.database as database_module
from app.core.database import Base
from app.models.orm import CurriculumVersion, Lesson, Unit
from app.services.curriculum import list_road
from content.scripts.import_seed import import_seed

SEED_PATH = ROOT / "content" / "seeds" / "beginner_v2.json"


@pytest_asyncio.fixture
async def road_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    previous_engine = database_module.engine
    previous_sessions = database_module.SessionLocal
    database_module.engine = engine
    database_module.SessionLocal = sessions
    await import_seed(SEED_PATH)

    try:
        yield sessions
    finally:
        database_module.engine = previous_engine
        database_module.SessionLocal = previous_sessions
        await engine.dispose()


@pytest.mark.asyncio
async def test_list_road_excludes_legacy_single_word_lessons(road_db):
    async with road_db() as session:
        version = (
            await session.execute(select(CurriculumVersion).limit(1))
        ).scalar_one()
        session.add(
            Lesson(
                id="v2-sound-04",
                unit_id="v2-unit-sound",
                title="水 · seoi2 · water",
                lesson_type="sound",
                sort_order=4,
                objectives=[],
                content_json={
                    "target": {
                        "traditional": "水",
                        "jyutping": "seoi2",
                        "english": "water",
                    },
                    "steps": [],
                },
                status="published",
            )
        )
        await session.commit()

        road = await list_road(session)
        assert len(road) == 10
        assert all(lesson.id != "v2-sound-04" for lesson in road)
        assert all(lesson.word_count >= 2 for lesson in road)
