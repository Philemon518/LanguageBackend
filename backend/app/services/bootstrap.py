"""Bootstrap curriculum seed on empty or stale database."""

import json
import logging
import sys
from pathlib import Path

from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("canto.bootstrap")


def resolve_seed_path() -> Path | None:
    source = Path(__file__).resolve()
    candidates = [
        Path("/app/content/seeds/beginner_v3.json"),
        source.parents[2] / "content" / "seeds" / "beginner_v3.json",
        source.parents[3] / "content" / "seeds" / "beginner_v3.json",
        Path.cwd() / "content" / "seeds" / "beginner_v3.json",
        Path.cwd().parent / "content" / "seeds" / "beginner_v3.json",
    ]
    return next((path for path in candidates if path.exists()), None)


def seed_expectations(seed_path: Path) -> tuple[str, int, int]:
    doc = json.loads(seed_path.read_text())
    return doc["version"], len(doc.get("units", [])), len(doc.get("lessons", []))


async def bootstrap_if_empty() -> None:
    seed_path = resolve_seed_path()
    if seed_path is None:
        logger.error("Curriculum seed not found")
        return

    logger.info("Curriculum seed: %s", seed_path)
    version, expected_units, expected_lessons = seed_expectations(seed_path)

    root = seed_path.parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from app.core.database import SessionLocal
    from content.scripts.import_seed import curriculum_is_ready, import_seed

    try:
        await import_seed(seed_path)
    except IntegrityError:
        async with SessionLocal() as session:
            if await curriculum_is_ready(session, version, expected_lessons):
                logger.warning(
                    "Curriculum bootstrap hit duplicate rows but version %s is ready",
                    version,
                )
                await _log_curriculum_shape(session)
                return
        logger.exception("Curriculum bootstrap failed on duplicate rows")
    except Exception:
        async with SessionLocal() as session:
            if await curriculum_is_ready(session, version, expected_lessons):
                logger.warning(
                    "Curriculum bootstrap failed but version %s is already present",
                    version,
                )
                await _log_curriculum_shape(session)
                return
        logger.exception("Curriculum bootstrap failed")

    async with SessionLocal() as session:
        await _log_curriculum_shape(session)
        lesson_count, unit_titles = await _curriculum_shape(session)
        if lesson_count < expected_lessons or len(unit_titles) < expected_units:
            logger.error(
                "Curriculum still behind seed: db has %s lessons / %s units, seed has %s / %s",
                lesson_count,
                len(unit_titles),
                expected_lessons,
                expected_units,
            )


async def ensure_seed_applied(db) -> None:
    """Re-import the seed when production is stuck on the 12-lesson v3 road."""
    seed_path = resolve_seed_path()
    if seed_path is None:
        return

    from sqlalchemy import select

    from app.models.orm import Unit

    unit_ids = set((await db.scalars(select(Unit.id))).all())
    if "v3-unit-2" in unit_ids:
        return
    if "v3-unit-0" not in unit_ids or "v3-unit-1" not in unit_ids:
        return

    logger.warning(
        "Curriculum missing Unit 2 (units=%s); reimporting %s",
        sorted(unit_ids),
        seed_path,
    )
    root = seed_path.parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from content.scripts.import_seed import import_seed

    await import_seed(seed_path)
    db.expire_all()


async def _curriculum_shape(session) -> tuple[int, list[str]]:
    from sqlalchemy import func, select

    from app.models.orm import Lesson, Unit

    lesson_count = await session.scalar(select(func.count()).select_from(Lesson)) or 0
    unit_titles = list(
        (await session.scalars(select(Unit.title).order_by(Unit.sort_order))).all()
    )
    return lesson_count, unit_titles


async def _log_curriculum_shape(session) -> None:
    lesson_count, unit_titles = await _curriculum_shape(session)
    logger.info(
        "Curriculum ready: %s lessons across units %s",
        lesson_count,
        unit_titles,
    )
