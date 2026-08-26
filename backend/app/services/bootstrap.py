"""Bootstrap curriculum seed on empty database."""

import logging
from pathlib import Path

from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("canto.bootstrap")


async def bootstrap_if_empty() -> None:
    source = Path(__file__).resolve()
    candidates = [
        source.parents[2] / "content" / "seeds" / "beginner_v3.json",  # /app in Docker
        source.parents[3] / "content" / "seeds" / "beginner_v3.json",  # monorepo checkout
    ]
    seed_path = next((path for path in candidates if path.exists()), candidates[0])
    if not seed_path.exists():
        logger.error(
            "Curriculum seed not found. Checked: %s", ", ".join(str(p) for p in candidates)
        )
        return

    # Inline import avoids making content generation part of the app package.
    import sys

    root = seed_path.parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from content.scripts.import_seed import curriculum_is_ready, import_seed

    import json

    doc = json.loads(seed_path.read_text())
    version = doc["version"]
    expected_lessons = len(doc.get("lessons", []))

    from app.core.database import SessionLocal

    try:
        await import_seed(seed_path)
    except IntegrityError:
        async with SessionLocal() as session:
            if await curriculum_is_ready(session, version, expected_lessons):
                logger.warning(
                    "Curriculum bootstrap hit duplicate rows but version %s is ready",
                    version,
                )
                return
        logger.exception("Curriculum bootstrap failed on duplicate rows")
        raise
    except Exception:
        async with SessionLocal() as session:
            if await curriculum_is_ready(session, version, expected_lessons):
                logger.warning(
                    "Curriculum bootstrap failed but version %s is already present",
                    version,
                )
                return
        logger.exception("Curriculum bootstrap failed")
        raise
