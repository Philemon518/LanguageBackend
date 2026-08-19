"""Bootstrap curriculum seed on empty database."""

from pathlib import Path


async def bootstrap_if_empty() -> None:
    source = Path(__file__).resolve()
    seed_path = next(
        (
            root / "content" / "seeds" / "beginner_v2.json"
            for root in (source.parents[2], source.parents[3])
            if (root / "content" / "seeds" / "beginner_v2.json").exists()
        ),
        source.parents[3] / "content" / "seeds" / "beginner_v2.json",
    )
    if not seed_path.exists():
        return

    # Inline import avoids making content generation part of the app package.
    import sys

    root = seed_path.parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from content.scripts.import_seed import import_seed

    await import_seed(seed_path)
