"""Test content validation."""

import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from content.scripts.generate_beginner_v2 import curriculum_expectations, generate_document

from content.scripts.validate import validate_jyutping, validate_seed_document

ROOT = Path(__file__).resolve().parents[2]
V1_PATH = ROOT / "content" / "seeds" / "beginner_v1.json"
V2_PATH = ROOT / "content" / "seeds" / "beginner_v2.json"
V2_EXPECTATIONS = curriculum_expectations()


def test_valid_jyutping():
    assert validate_jyutping("seoi2") == []
    assert validate_jyutping("ping4 gwo2") == []


def test_invalid_jyutping():
    assert validate_jyutping("seoi") != []


def test_v1_seed_document_remains_valid():
    doc = json.loads(V1_PATH.read_text())
    errors = validate_seed_document(doc)
    assert errors == [], f"Seed errors: {errors}"


def test_v2_seed_document_is_generated_deterministically():
    doc = json.loads(V2_PATH.read_text())
    assert doc == generate_document()
    errors = validate_seed_document(doc)
    assert errors == [], f"Seed errors: {errors}"


def test_v2_exact_curriculum_counts():
    doc = generate_document()
    lessons = doc["lessons"]
    steps = [step for lesson in lessons for step in lesson["content"]["steps"]]
    expectations = curriculum_expectations()

    assert len(lessons) == expectations["lesson_count"]
    assert Counter(lesson["lesson_type"] for lesson in lessons) == expectations["lesson_types"]
    assert all(20 <= len(lesson["content"]["steps"]) <= 35 for lesson in lessons)
    assert Counter(step["skill"] for step in steps) == expectations["skills"]
    assert Counter(step["type"] for step in steps) == expectations["exercise_types"]


def test_v2_every_lesson_introduces_multiple_words_before_practice():
    doc = generate_document()
    for lesson in doc["lessons"]:
        steps = lesson["content"]["steps"]
        intro_steps = []
        for step in steps:
            if step["type"] != "word_intro":
                break
            intro_steps.append(step)
        assert 3 <= len(intro_steps) <= 4
        assert len(lesson["content"]["target"]["words"]) == len(intro_steps)


def test_v2_cloze_choices_use_lesson_vocabulary():
    doc = generate_document()
    for step in (
        step
        for lesson in doc["lessons"]
        for step in lesson["content"]["steps"]
        if step["type"] == "cloze"
    ):
        lesson_words = step["metadata"]["lesson_words"]
        option_labels = [option["label"] for option in step["options"]]
        assert all(label in lesson_words for label in option_labels)


def test_v2_beginner_writing_uses_choices_and_sentence_building():
    doc = generate_document()
    steps = [step for lesson in doc["lessons"] for step in lesson["content"]["steps"]]

    assert not any(step["type"] == "dictation" for step in steps)
    for step in (step for step in steps if step["type"] == "cloze"):
        assert step["reveal_english"]
        assert step["correct_option_id"] == "cloze-correct"
        assert step["metadata"]["allow_manual_input"] is True
        assert len(step["options"]) >= 3


def test_v2_validation_rejects_count_and_duplicate_id_errors():
    doc = generate_document()
    doc["lessons"].pop()
    doc["lessons"][1]["id"] = doc["lessons"][0]["id"]

    errors = validate_seed_document(doc)
    assert any(f"exactly {V2_EXPECTATIONS['lesson_count']} lessons" in error for error in errors)
    assert any("Duplicate lesson IDs" in error for error in errors)


def test_v2_validation_rejects_bad_prerequisite_and_answer():
    doc = generate_document()
    doc["lessons"][2]["prerequisites"] = ["missing-lesson"]
    first_step = doc["lessons"][0]["content"]["steps"][0]
    first_step["correct_option_id"] = "missing-option"

    errors = validate_seed_document(doc)
    assert any("unknown prerequisite missing-lesson" in error for error in errors)
    assert any("correct_option_id is not an option" in error for error in errors)


def test_v2_validation_rejects_missing_audio_and_skill():
    doc = generate_document()
    first_step = doc["lessons"][0]["content"]["steps"][0]
    first_step["audio"]["text"] = ""
    doc["lessons"][0]["content"]["steps"][4]["skill"] = ["listening"]

    errors = validate_seed_document(doc)
    assert any("exactly one valid skill" in error for error in errors)
    assert any("requires audio text" in error for error in errors)


def test_v2_validation_rejects_invalid_tone_metadata():
    doc = deepcopy(generate_document())
    doc["lexemes"][0]["tone"] = 6
    doc["lessons"][0]["content"]["target"]["tones"] = [6]

    errors = validate_seed_document(doc)
    assert any("tone must match" in error for error in errors)
    assert any("tones must exactly match Jyutping" in error for error in errors)
