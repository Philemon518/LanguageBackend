"""Import seed curriculum into the database."""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

from sqlalchemy import select

# Add backend to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.core.database import Base, SessionLocal, engine
from app.models.orm import Character, CurriculumVersion, Lesson, Lexeme, Unit
from content.scripts.validate import validate_seed_document


async def import_seed(seed_path: Path, version: str | None = None) -> None:
    doc = json.loads(seed_path.read_text())
    version = version or doc["version"]
    seed_hash = hashlib.sha256(
        json.dumps(doc, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    errors = validate_seed_document(doc)
    if errors:
        raise ValueError("Validation failed:\n" + "\n".join(errors))

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        existing = await db.execute(
            select(CurriculumVersion).where(CurriculumVersion.version == version)
        )
        existing_version = existing.scalar_one_or_none()
        if existing_version:
            if (existing_version.metadata_json or {}).get("seed_hash") == seed_hash:
                print(f"Version {version} already up to date")
                return

            for lex in doc.get("lexemes", []):
                row = await db.get(Lexeme, lex["id"])
                if row:
                    row.traditional = lex["traditional"]
                    row.jyutping = lex["jyutping"]
                    row.tone = lex["tone"]
                    row.english = lex["english"]
                    row.tags = lex.get("tags", [])
                    row.difficulty = lex.get("difficulty", 1)

            for lesson_data in doc["lessons"]:
                row = await db.get(Lesson, lesson_data["id"])
                if row:
                    row.title = lesson_data["title"]
                    row.lesson_type = lesson_data["lesson_type"]
                    row.sort_order = lesson_data["sort_order"]
                    row.objectives = lesson_data.get("objectives", [])
                    row.content_json = lesson_data["content"]

            existing_version.metadata_json = {
                **(existing_version.metadata_json or {}),
                "seed_hash": seed_hash,
            }
            await db.commit()
            print(f"Updated version {version} from changed seed content")
            return

        cv = CurriculumVersion(
            version=version,
            level=doc["level"],
            status="published",
            metadata_json={"seed_hash": seed_hash},
        )
        db.add(cv)
        await db.flush()

        for unit_data in doc["units"]:
            db.add(
                Unit(
                    id=unit_data["id"],
                    curriculum_version_id=cv.id,
                    title=unit_data["title"],
                    phase=unit_data["phase"],
                    sort_order=unit_data["sort_order"],
                    prerequisites=unit_data.get("prerequisites", []),
                )
            )

        for lex in doc.get("lexemes", []):
            db.add(
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
            db.add(
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

        for lesson_data in doc["lessons"]:
            db.add(
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

        await db.commit()
        print(f"Imported {len(doc['lessons'])} lessons, {len(doc.get('lexemes', []))} lexemes")


def main() -> None:
    seed = ROOT / "content" / "seeds" / "beginner_v2.json"
    asyncio.run(import_seed(seed))


if __name__ == "__main__":
    main()
