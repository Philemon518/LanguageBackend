"""Beginner acceptance verification checks."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))


def check_seed() -> None:
    from content.scripts.validate import validate_seed_document

    seed = json.loads((ROOT / "content/seeds/beginner_v1.json").read_text())
    errors = validate_seed_document(seed)
    assert not errors, errors
    assert len(seed["lessons"]) >= 6, "Expected full beginner curriculum"
    phases = {u["phase"] for u in seed["units"]}
    for expected in ("sound", "components", "vocabulary", "sentences", "integrated"):
        assert expected in phases, f"Missing phase: {expected}"


def check_backend_tests() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        cwd=ROOT / "backend",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def check_exercise_types() -> None:
    seed = json.loads((ROOT / "content/seeds/beginner_v1.json").read_text())
    types = set()
    skills = set()
    for lesson in seed["lessons"]:
        for step in lesson["content"]["steps"]:
            types.add(step["type"])
            skills.add(step["skill"])
    for t in ("select_tone", "select_meaning", "speak", "write_sentence", "dictation"):
        assert t in types, f"Missing exercise type: {t}"
    for s in ("listening", "speaking", "reading", "writing"):
        assert s in skills, f"Missing skill: {s}"


def main() -> None:
    check_seed()
    check_exercise_types()
    check_backend_tests()
    print("Beginner verification: PASS")


if __name__ == "__main__":
    main()
