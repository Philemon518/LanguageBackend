"""CLI validation check for CI."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from content.scripts.validate import validate_seed_document


def main() -> None:
    seed_paths = [
        ROOT / "content" / "seeds" / "beginner_v1.json",
        ROOT / "content" / "seeds" / "beginner_v2.json",
        ROOT / "content" / "seeds" / "beginner_v3.json",
    ]
    all_errors = []
    for seed in seed_paths:
        doc = json.loads(seed.read_text())
        all_errors.extend(f"{seed.name}: {error}" for error in validate_seed_document(doc))
    if all_errors:
        print("\n".join(all_errors))
        sys.exit(1)
    print(f"Seed validation OK ({len(seed_paths)} files)")


if __name__ == "__main__":
    main()
