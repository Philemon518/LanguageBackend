"""Import seed curriculum into the database."""

import asyncio
import hashlib
import json
import logging
import sys
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

# Add backend to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.core import database as db
from app.models.orm import Character, CurriculumVersion, Lesson, Lexeme, Unit
from content.scripts.validate import validate_seed_document

logger = logging.getLogger("canto.import_seed")
SEED_LOCK_ID = 8_192_001


def _seed_lesson_ids(doc: dict) -> set[str]:
    return {lesson["id"] for lesson in doc.get("lessons", [])}


async def _db_lesson_ids(session, unit_ids: list[str]) -> set[str]:
    if not unit_ids:
        return set()
    result = await session.scalars(select(Lesson.id).where(Lesson.unit_id.in_(unit_ids)))
    return set(result.all())


async def curriculum_is_ready(session, version: str, expected_lessons: int) -> bool:
    existing_version = await session.scalar(
        select(CurriculumVersion).where(CurriculumVersion.version == version)
    )
    if existing_version is None:
        return False

    unit_present = await session.scalar(
        select(Unit.id)
        .where(Unit.curriculum_version_id == existing_version.id)
        .limit(1)
    )
    if unit_present is None:
        return False

    lesson_count = await session.scalar(select(func.count()).select_from(Lesson))
    return bool(lesson_count and lesson_count >= expected_lessons)


def _apply_character_fields(row: Character, char: dict) -> None:
    row.glyph = char["glyph"]
    row.meaning = char["meaning"]
    row.jyutping = char["jyutping"]
    row.tone = char["tone"]
    row.radical = char.get("radical")
    row.components = char.get("components", [])
    row.related_words = char.get("related_words", [])


async def _upsert_character(session, char: dict) -> None:
    row = await session.scalar(select(Character).where(Character.id == char["id"]))
    if row:
        _apply_character_fields(row, char)
        return

    existing = await session.scalar(select(Character).where(Character.glyph == char["glyph"]))
    if existing:
        _apply_character_fields(existing, char)
        return

    session.add(
        Character(
            id=char["id"],
            glyph=char["glyph"],
            meaning=char["meaning"],
            jyutping=char["jyutping"],
            tone=char["tone"],
            radical=char.get("radical"),
            components=char.get("components", []),
            related_words=char.get("related_words", []),
            status="published",
        )
    )


async def _upsert_lexeme(session, lex: dict) -> None:
    row = await session.scalar(select(Lexeme).where(Lexeme.id == lex["id"]))
    if row:
        row.traditional = lex["traditional"]
        row.jyutping = lex.get("jyutping") or ""
        row.tone = lex.get("tone") or 0
        row.english = lex["english"]
        row.tags = lex.get("tags", [])
        row.difficulty = lex.get("difficulty", 1)
        return

    session.add(
        Lexeme(
            id=lex["id"],
            traditional=lex["traditional"],
            jyutping=lex.get("jyutping") or "",
            tone=lex.get("tone") or 0,
            english=lex["english"],
            tags=lex.get("tags", []),
            difficulty=lex.get("difficulty", 1),
            status="published",
        )
    )


async def _upsert_unit(session, curriculum_version_id, unit_data: dict) -> None:
    row = await session.scalar(select(Unit).where(Unit.id == unit_data["id"]))
    if row:
        row.curriculum_version_id = curriculum_version_id
        row.title = unit_data["title"]
        row.phase = unit_data["phase"]
        row.sort_order = unit_data["sort_order"]
        row.prerequisites = unit_data.get("prerequisites", [])
        return

    session.add(
        Unit(
            id=unit_data["id"],
            curriculum_version_id=curriculum_version_id,
            title=unit_data["title"],
            phase=unit_data["phase"],
            sort_order=unit_data["sort_order"],
            prerequisites=unit_data.get("prerequisites", []),
        )
    )


async def _upsert_lesson(session, lesson_data: dict) -> None:
    row = await session.scalar(select(Lesson).where(Lesson.id == lesson_data["id"]))
    if row:
        row.unit_id = lesson_data["unit_id"]
        row.title = lesson_data["title"]
        row.lesson_type = lesson_data["lesson_type"]
        row.sort_order = lesson_data["sort_order"]
        row.objectives = lesson_data.get("objectives", [])
        row.content_json = lesson_data["content"]
        return

    session.add(
        Lesson(
            id=lesson_data["id"],
            unit_id=lesson_data["unit_id"],
            title=lesson_data["title"],
            lesson_type=lesson_data["lesson_type"],
            sort_order=lesson_data["sort_order"],
            objectives=lesson_data.get("objectives", []),
            content_json=lesson_data["content"],
            status="published",
        )
    )


async def _sync_seed_document(session, doc: dict, version: str, seed_hash: str) -> bool:
    """Synchronize seed content into the database.

    Returns True when content was changed, False when already up to date.
    """
    unit_ids = [unit["id"] for unit in doc.get("units", [])]
    seed_lesson_ids = _seed_lesson_ids(doc)

    with session.no_autoflush:
        existing_version = await session.scalar(
            select(CurriculumVersion).where(CurriculumVersion.version == version)
        )
        if existing_version:
            units_present = await session.scalar(
                select(Unit.id)
                .where(Unit.curriculum_version_id == existing_version.id)
                .limit(1)
            )
            if units_present is not None:
                db_lesson_ids = await _db_lesson_ids(session, unit_ids)
                hash_matches = (existing_version.metadata_json or {}).get("seed_hash") == seed_hash
                if hash_matches and db_lesson_ids == seed_lesson_ids:
                    logger.info("Version %s already up to date", version)
                    return False
                if hash_matches:
                    logger.warning(
                        "Version %s hash matches but %s lessons in db vs %s in seed; reconciling",
                        version,
                        len(db_lesson_ids),
                        len(seed_lesson_ids),
                    )
            else:
                logger.warning(
                    "Version %s exists without linked units; reconciling seed units",
                    version,
                )
        else:
            existing_version = CurriculumVersion(
                id=uuid4(),
                version=version,
                level=doc["level"],
                status="published",
                metadata_json={"seed_hash": seed_hash},
            )
            session.add(existing_version)

        for unit_data in doc.get("units", []):
            await _upsert_unit(session, existing_version.id, unit_data)

        for lex in doc.get("lexemes", []):
            await _upsert_lexeme(session, lex)

        for char in doc.get("characters", []):
            await _upsert_character(session, char)

        if unit_ids:
            stale_lessons = await session.execute(
                select(Lesson).where(Lesson.unit_id.in_(unit_ids))
            )
            for lesson in stale_lessons.scalars():
                if lesson.id not in seed_lesson_ids:
                    await session.delete(lesson)

        for lesson_data in doc.get("lessons", []):
            await _upsert_lesson(session, lesson_data)

        existing_version.metadata_json = {
            **(existing_version.metadata_json or {}),
            "seed_hash": seed_hash,
        }
    return True


async def _commit_seed_sync(session, doc: dict, version: str, seed_hash: str) -> None:
    changed = await _sync_seed_document(session, doc, version, seed_hash)
    if not changed:
        return

    await session.flush()
    await session.commit()
    logger.info(
        "Synchronized version %s (%s lessons, %s lexemes)",
        version,
        len(doc.get("lessons", [])),
        len(doc.get("lexemes", [])),
    )


async def import_seed(seed_path: Path, version: str | None = None) -> None:
    doc = json.loads(seed_path.read_text())
    version = version or doc["version"]
    seed_hash = hashlib.sha256(
        json.dumps(doc, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    errors = validate_seed_document(doc)
    if errors:
        raise ValueError("Validation failed:\n" + "\n".join(errors))

    expected_lessons = len(doc.get("lessons", []))

    async with db.SessionLocal() as session:
        if db.engine.dialect.name == "postgresql":
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": SEED_LOCK_ID},
            )

        try:
            await _commit_seed_sync(session, doc, version, seed_hash)
        except IntegrityError:
            await session.rollback()
            if await curriculum_is_ready(session, version, expected_lessons):
                logger.info(
                    "Version %s already present after duplicate-key conflict",
                    version,
                )
                return

            if db.engine.dialect.name == "postgresql":
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_id)"),
                    {"lock_id": SEED_LOCK_ID},
                )
            await _commit_seed_sync(session, doc, version, seed_hash)


def main() -> None:
    seed = ROOT / "content" / "seeds" / "beginner_v3.json"
    asyncio.run(import_seed(seed))


if __name__ == "__main__":
    main()
