"""Tests for curriculum road filtering."""

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import app.core.database as database_module
from app.core.database import Base
from app.services.curriculum import list_road
from content.scripts.import_seed import import_seed

SEED_PATH = ROOT / "content" / "seeds" / "beginner_v3.json"


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
async def test_list_road_returns_v3_foundations_in_curriculum_order(road_db):
    async with road_db() as session:
        road = await list_road(session)
        assert len(road) == 18
        assert [lesson.id for lesson in road[:2]] == ["v3-orientation", "v3-tones"]
        assert [lesson.id for lesson in road[2:12]] == [
            *(f"v3-number-{number:02d}" for number in range(1, 9)),
            "v3-number-review",
            "v3-number-challenge",
        ]
        assert [lesson.id for lesson in road[12:]] == [
            *(f"v3-intro-{index:02d}" for index in range(1, 6)),
            "v3-intro-review",
        ]
        assert [lesson.global_order for lesson in road] == list(range(18))
        assert [lesson.lesson_type for lesson in road] == [
            "orientation",
            "tone",
            *(["number"] * 8),
            "number_review",
            "number_challenge",
            *(["introduction"] * 5),
            "introduction_review",
        ]
        assert [lesson.word_count for lesson in road[2:10]] == list(range(3, 11))
