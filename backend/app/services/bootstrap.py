"""Bootstrap curriculum seed on empty database."""

import logging
from pathlib import Path

logger = logging.getLogger("canto.bootstrap")


async def bootstrap_if_empty() -> None:
    source = Path(__file__).resolve()
    candidates = [
        source.parents[2] / "content" / "seeds" / "beginner_v2.json",  # /app in Docker
        source.parents[3] / "content" / "seeds" / "beginner_v2.json",  # monorepo checkout
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
    from content.scripts.import_seed import import_seed

    try:
        await import_seed(seed_path)
    except Exception:
        logger.exception("Curriculum bootstrap failed")
        raise
