"""Import seed curriculum into the database."""

import asyncio
import hashlib
import json
import logging
import sys
from contextlib import suppress
from pathlib import Path

from sqlalchemy import select, text
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


async def import_seed(seed_path: Path, version: str | None = None) -> None:
    doc = json.loads(seed_path.read_text())
    version = version or doc["version"]
    seed_hash = hashlib.sha256(
        json.dumps(doc, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    errors = validate_seed_document(doc)
    if errors:
        raise ValueError("Validation failed:\n" + "\n".join(errors))

    async with db.SessionLocal() as session:
        if db.engine.dialect.name == "postgresql":
            await session.execute(
                text("SELECT pg_advisory_lock(:lock_id)"),
                {"lock_id": SEED_LOCK_ID},
            )
        try:
            existing = await session.execute(
                select(CurriculumVersion).where(CurriculumVersion.version == version)
            )
            existing_version = existing.scalar_one_or_none()
            if existing_version:
                units_present = await session.execute(
                    select(Unit.id)
                    .where(Unit.curriculum_version_id == existing_version.id)
                    .limit(1)
                )
                if units_present.scalar_one_or_none() is None:
                    logger.warning(
                        "Version %s exists without units; removing incomplete import",
                        version,
                    )
                    await session.delete(existing_version)
                    await session.flush()
                    existing_version = None

            if existing_version:
                if (existing_version.metadata_json or {}).get("seed_hash") == seed_hash:
                    logger.info("Version %s already up to date", version)
                    return

                unit_ids = [unit["id"] for unit in doc.get("units", [])]
                seed_lesson_ids = {lesson["id"] for lesson in doc.get("lessons", [])}

                for unit_data in doc.get("units", []):
                    row = await session.get(Unit, unit_data["id"])
                    if row:
                        row.title = unit_data["title"]
                        row.phase = unit_data["phase"]
                        row.sort_order = unit_data["sort_order"]
                        row.prerequisites = unit_data.get("prerequisites", [])

                for lex in doc.get("lexemes", []):
                    row = await session.get(Lexeme, lex["id"])
                    if row:
                        row.traditional = lex["traditional"]
                        row.jyutping = lex["jyutping"]
                        row.tone = lex["tone"]
                        row.english = lex["english"]
                        row.tags = lex.get("tags", [])
                        row.difficulty = lex.get("difficulty", 1)
                    else:
                        session.add(
                            Lexeme(
                                id=lex["id"],
                                traditional=lex["traditional"],
                                jyutping=lex["jyutping"],
                                tone=lex["tone"],
                                english=lex["english"],
                                tags=lex.get("tags", []),
                                difficulty=lex.get("difficulty", 1),
                                status="published",
                            )
                        )

                for char in doc.get("characters", []):
                    row = await session.get(Character, char["id"])
                    if row:
                        row.glyph = char["glyph"]
                        row.meaning = char["meaning"]
                        row.jyutping = char["jyutping"]
                        row.tone = char["tone"]
                        row.radical = char.get("radical")
                        row.components = char.get("components", [])
                        row.related_words = char.get("related_words", [])
                    else:
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

                stale_lessons = await session.execute(
                    select(Lesson).where(Lesson.unit_id.in_(unit_ids))
                )
                for lesson in stale_lessons.scalars():
                    if lesson.id not in seed_lesson_ids:
                        await session.delete(lesson)

                for lesson_data in doc.get("lessons", []):
                    row = await session.get(Lesson, lesson_data["id"])
                    if row:
                        row.unit_id = lesson_data["unit_id"]
                        row.title = lesson_data["title"]
                        row.lesson_type = lesson_data["lesson_type"]
                        row.sort_order = lesson_data["sort_order"]
                        row.objectives = lesson_data.get("objectives", [])
                        row.content_json = lesson_data["content"]
                    else:
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

                existing_version.metadata_json = {
                    **(existing_version.metadata_json or {}),
                    "seed_hash": seed_hash,
                }
                await session.commit()
                logger.info(
                    "Updated version %s from changed seed content (%s lessons)",
                    version,
                    len(doc.get("lessons", [])),
                )
                return

            cv = CurriculumVersion(
                version=version,
                level=doc["level"],
                status="published",
                metadata_json={"seed_hash": seed_hash},
            )
            session.add(cv)
            await session.flush()

            for unit_data in doc["units"]:
                session.add(
                    Unit(
                        id=unit_data["id"],
                        curriculum_version_id=cv.id,
                        title=unit_data["title"],
                        phase=unit_data["phase"],
                        sort_order=unit_data["sort_order"],
                        prerequisites=unit_data.get("prerequisites", []),
                    )
                )
            await session.flush()

            for lex in doc.get("lexemes", []):
                session.add(
                    Lexeme(
                        id=lex["id"],
                        traditional=lex["traditional"],
                        jyutping=lex["jyutping"],
                        tone=lex["tone"],
                        english=lex["english"],
                        tags=lex.get("tags", []),
                        difficulty=lex.get("difficulty", 1),
                        status="published",
                    )
                )

            for char in doc.get("characters", []):
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
            await session.flush()

            for lesson_data in doc["lessons"]:
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

            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                retry = await session.execute(
                    select(CurriculumVersion.id).where(CurriculumVersion.version == version)
                )
                if retry.scalar_one_or_none() is not None:
                    logger.info(
                        "Version %s imported by another worker during startup", version
                    )
                    return
                raise
            logger.info(
                "Imported %s lessons and %s lexemes",
                len(doc["lessons"]),
                len(doc.get("lexemes", [])),
            )
        finally:
            if db.engine.dialect.name == "postgresql":
                with suppress(Exception):
                    await session.execute(
                        text("SELECT pg_advisory_unlock(:lock_id)"),
                        {"lock_id": SEED_LOCK_ID},
                    )


def main() -> None:
    seed = ROOT / "content" / "seeds" / "beginner_v2.json"
    asyncio.run(import_seed(seed))


if __name__ == "__main__":
    main()
