"""Tests for curriculum seed import synchronization."""

import json
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import app.core.database as database_module
from app.core.database import Base
from app.models.orm import CurriculumVersion, Lesson
from content.scripts.generate_beginner_v2 import generate_document
from content.scripts.import_seed import import_seed


@pytest_asyncio.fixture
async def import_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    previous_engine = database_module.engine
    previous_sessions = database_module.SessionLocal
    database_module.engine = engine
    database_module.SessionLocal = sessions
    try:
        yield sessions
    finally:
        database_module.engine = previous_engine
        database_module.SessionLocal = previous_sessions
        await engine.dispose()


@pytest.mark.asyncio
async def test_import_seed_removes_stale_lessons_on_update(import_db, tmp_path):
    seed_path = tmp_path / "beginner_v2.json"
    doc = generate_document()
    seed_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    await import_seed(seed_path)

    async with import_db() as session:
        count = await session.scalar(select(func.count()).select_from(Lesson))
        assert count == 10

        stale = Lesson(
            id="v2-sound-99",
            unit_id="v2-unit-sound",
            title="Stale lesson",
            lesson_type="sound",
            sort_order=99,
            objectives=[],
            content_json={"steps": []},
            status="published",
        )
        session.add(stale)
        version = await session.scalar(
            select(CurriculumVersion).where(CurriculumVersion.version == "2.0.0")
        )
        version.metadata_json = {"seed_hash": "outdated-hash"}
        await session.commit()

    await import_seed(seed_path)

    async with import_db() as session:
        lesson_ids = (
            await session.scalars(select(Lesson.id).order_by(Lesson.id))
        ).all()
        assert len(lesson_ids) == 10
        assert "v2-sound-99" not in lesson_ids

        version = await session.scalar(
            select(CurriculumVersion).where(CurriculumVersion.version == "2.0.0")
        )
        assert version is not None
        assert version.metadata_json.get("seed_hash") != "outdated-hash"
