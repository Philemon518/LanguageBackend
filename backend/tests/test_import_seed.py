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
from uuid import uuid4

from app.models.orm import Character, CurriculumVersion, Lesson, Unit
from content.scripts.generate_beginner_v2 import generate_document
from content.scripts.generate_beginner_v3 import generate_document as generate_v3_document
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
        lesson_ids = (await session.scalars(select(Lesson.id).order_by(Lesson.id))).all()
        assert len(lesson_ids) == 10
        assert "v2-sound-99" not in lesson_ids

        version = await session.scalar(
            select(CurriculumVersion).where(CurriculumVersion.version == "2.0.0")
        )
        assert version is not None
        assert version.metadata_json.get("seed_hash") != "outdated-hash"


@pytest.mark.asyncio
async def test_import_seed_reconciles_when_hash_matches_but_lessons_differ(import_db, tmp_path):
    seed_path = tmp_path / "beginner_v2.json"
    doc = generate_document()
    seed_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    await import_seed(seed_path)

    async with import_db() as session:
        version = await session.scalar(
            select(CurriculumVersion).where(CurriculumVersion.version == "2.0.0")
        )
        current_hash = version.metadata_json["seed_hash"]
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
        version.metadata_json = {"seed_hash": current_hash}
        await session.commit()

    await import_seed(seed_path)

    async with import_db() as session:
        lesson_ids = set((await session.scalars(select(Lesson.id))).all())
        assert len(lesson_ids) == 10
        assert "v2-sound-04" not in lesson_ids


@pytest.mark.asyncio
async def test_import_seed_upserts_characters_by_glyph(import_db, tmp_path):
    seed_path = tmp_path / "beginner_v2.json"
    doc = generate_document()
    seed_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    async with import_db() as session:
        from uuid import uuid4

        from app.models.orm import Unit

        cv = CurriculumVersion(id=uuid4(), version="2.0.0", level="beginner", metadata_json={})
        session.add(cv)
        await session.flush()
        session.add(
            Unit(
                id="v2-unit-sound",
                curriculum_version_id=cv.id,
                title="Sound",
                phase="sound",
                sort_order=1,
            )
        )
        session.add(
            Character(
                id="legacy-character-xiu",
                glyph="休",
                meaning="old rest",
                jyutping="jau1",
                tone=1,
                status="published",
            )
        )
        await session.commit()

    await import_seed(seed_path)

    async with import_db() as session:
        by_glyph = await session.scalar(select(Character).where(Character.glyph == "休"))
        assert by_glyph is not None
        assert by_glyph.meaning == "rest"
        assert (
            await session.scalar(
                select(func.count()).select_from(Character).where(Character.glyph == "休")
            )
            == 1
        )


@pytest.mark.asyncio
async def test_import_seed_imports_beginner_v3_foundation_road(import_db, tmp_path):
    seed_path = tmp_path / "beginner_v3.json"
    seed_path.write_text(
        json.dumps(generate_v3_document(), ensure_ascii=False),
        encoding="utf-8",
    )

    await import_seed(seed_path)

    async with import_db() as session:
        version = await session.scalar(
            select(CurriculumVersion).where(CurriculumVersion.version == "3.0.0")
        )
        lessons = (await session.scalars(select(Lesson))).all()
        assert version is not None
        assert len(lessons) == 12
        assert sum(lesson.unit_id == "v3-unit-0" for lesson in lessons) == 2
        assert sum(lesson.unit_id == "v3-unit-1" for lesson in lessons) == 10


@pytest.mark.asyncio
async def test_import_seed_v3_import_is_idempotent(import_db, tmp_path):
    seed_path = tmp_path / "beginner_v3.json"
    seed_path.write_text(
        json.dumps(generate_v3_document(), ensure_ascii=False),
        encoding="utf-8",
    )

    await import_seed(seed_path)
    await import_seed(seed_path)

    async with import_db() as session:
        versions = (await session.scalars(select(CurriculumVersion))).all()
        lessons = (await session.scalars(select(Lesson))).all()
        assert len(versions) == 1
        assert len(lessons) == 12


@pytest.mark.asyncio
async def test_import_seed_reconciles_orphaned_v3_units(import_db, tmp_path):
    seed_path = tmp_path / "beginner_v3.json"
    doc = generate_v3_document()
    seed_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    async with import_db() as session:
        orphan_cv = CurriculumVersion(
            id=uuid4(),
            version="9.9.9",
            level="beginner",
            metadata_json={},
        )
        session.add(orphan_cv)
        await session.flush()
        session.add(
            Unit(
                id="v3-unit-0",
                curriculum_version_id=orphan_cv.id,
                title="廣東話",
                phase="orientation",
                sort_order=0,
            )
        )
        session.add(
            CurriculumVersion(
                id=uuid4(),
                version="3.0.0",
                level="beginner",
                metadata_json={},
            )
        )
        await session.commit()

    await import_seed(seed_path)

    async with import_db() as session:
        version = await session.scalar(
            select(CurriculumVersion).where(CurriculumVersion.version == "3.0.0")
        )
        unit = await session.get(Unit, "v3-unit-0")
        lessons = (await session.scalars(select(Lesson))).all()
        assert version is not None
        assert unit is not None
        assert unit.curriculum_version_id == version.id
        assert len(lessons) == 12
