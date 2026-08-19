"""Content validation utilities."""

import re
from collections import Counter

JYUTPING_SYLLABLE = re.compile(r"^[a-z]+[1-6]$", re.IGNORECASE)
HAN_CHARACTER = re.compile(r"[\u3400-\u9fff]")
TONE_VALID = {1, 2, 3, 4, 5, 6}
SKILLS = {"listening", "speaking", "reading", "writing"}
CHOICE_TYPES = {
    "select_tone",
    "select_meaning",
    "select_jyutping",
    "select_character",
    "match",
    "word_intro",
}
SUPPORTED_TYPES = CHOICE_TYPES | {
    "order_words",
    "cloze",
    "dictation",
    "speak",
    "write_sentence",
}
SIMPLIFIED_ONLY = set("这们个为么说从东丝乐习买车过边师学语时间见饭饮书")
V2_LESSON_TYPES = {"sound": 12, "component": 8, "vocabulary": 12, "grammar": 8}
V2_SKILLS = {"listening": 92, "speaking": 40, "reading": 69, "writing": 120}
V2_EXERCISE_TYPES = {
    "select_meaning": 40,
    "select_jyutping": 40,
    "speak": 40,
    "select_character": 40,
    "select_tone": 12,
    "match": 28,
    "cloze": 40,
    "order_words": 40,
    "dictation": 40,
    "word_intro": 1,
}


def validate_jyutping(jyutping: str) -> list[str]:
    errors: list[str] = []
    if not jyutping.strip():
        errors.append("Empty jyutping")
        return errors
    for syllable in jyutping.strip().split():
        if not JYUTPING_SYLLABLE.match(syllable):
            errors.append(f"Invalid jyutping syllable: {syllable}")
    return errors


def _tone_values(jyutping: str) -> list[int]:
    return [int(syllable[-1]) for syllable in jyutping.strip().split()]


def _validate_traditional(value: str, label: str) -> list[str]:
    errors: list[str] = []
    if not value or not HAN_CHARACTER.search(value):
        errors.append(f"{label} must contain Traditional Chinese text")
    simplified = sorted(set(value) & SIMPLIFIED_ONLY)
    if simplified:
        errors.append(f"{label} contains simplified-only characters: {''.join(simplified)}")
    return errors


def _validate_tone_metadata(item: dict, label: str, require_tones: bool = False) -> list[str]:
    errors = validate_jyutping(item.get("jyutping", ""))
    if errors:
        return [f"{label}: {error}" for error in errors]
    expected = _tone_values(item["jyutping"])
    if item.get("tone") not in TONE_VALID:
        errors.append(f"{label}: invalid tone {item.get('tone')}")
    elif item["tone"] != expected[-1]:
        errors.append(f"{label}: tone must match the final Jyutping syllable")
    if require_tones and item.get("tones") != expected:
        errors.append(f"{label}: tones must exactly match Jyutping")
    return errors


def validate_lexeme(lexeme: dict) -> list[str]:
    errors: list[str] = []
    for field in ("id", "traditional", "jyutping", "english"):
        if not lexeme.get(field):
            errors.append(f"Missing field: {field}")
    errors.extend(_validate_tone_metadata(lexeme, f"Lexeme {lexeme.get('id')}"))
    return errors


def _validate_step(step: dict, lesson_id: str) -> list[str]:
    sid = step.get("id")
    label = f"Step {sid} in lesson {lesson_id}"
    errors: list[str] = []
    exercise_type = step.get("type")
    skill = step.get("skill")
    if not sid:
        errors.append(f"Lesson {lesson_id} has a step without an id")
    if exercise_type not in SUPPORTED_TYPES:
        errors.append(f"{label} has unsupported type {exercise_type}")
    if not isinstance(skill, str) or skill not in SKILLS:
        errors.append(f"{label} must have exactly one valid skill")
    if not step.get("prompt"):
        errors.append(f"{label} has no prompt")

    options = step.get("options", [])
    option_ids = [option.get("id") for option in options]
    if len(option_ids) != len(set(option_ids)) or any(not option_id for option_id in option_ids):
        errors.append(f"{label} has missing or duplicate option IDs")
    if exercise_type in CHOICE_TYPES:
        correct = step.get("correct_option_id")
        if not options:
            errors.append(f"{label} has no options")
        if not correct:
            errors.append(f"{label} missing correct_option_id")
        elif correct not in option_ids:
            errors.append(f"{label} correct_option_id is not an option")
    if exercise_type == "select_jyutping":
        for option in options:
            errors.extend(
                f"{label} option {option.get('id')}: {error}"
                for error in validate_jyutping(option.get("jyutping", ""))
            )
    metadata = step.get("metadata") or {}
    if exercise_type == "order_words":
        expected = metadata.get("expected_order")
        if not expected or expected != option_ids or len(expected) != len(set(expected)):
            errors.append(f"{label} expected_order must exactly cover options")
    if exercise_type == "cloze" and not metadata.get("expected"):
        errors.append(f"{label} missing expected cloze answer")
    if exercise_type in {"dictation", "speak"}:
        expected = metadata.get("expected") or step.get("reveal_jyutping")
        if not expected:
            errors.append(f"{label} missing expected Jyutping")
        else:
            errors.extend(f"{label}: {error}" for error in validate_jyutping(expected))
    if exercise_type == "write_sentence" and (
        not metadata.get("expected_patterns") or not metadata.get("target_vocab")
    ):
        errors.append(f"{label} missing writing answer metadata")

    audio_text = (step.get("audio") or {}).get("text")
    if (
        skill == "listening"
        or exercise_type in {"dictation", "word_intro"}
    ) and not audio_text:
        errors.append(f"{label} requires audio text")
    return errors


def validate_lesson(lesson: dict, *, require_v2: bool = False) -> list[str]:
    errors: list[str] = []
    for field in ("id", "unit_id", "title", "content"):
        if not lesson.get(field):
            errors.append(f"Lesson missing: {field}")
    steps = lesson.get("content", {}).get("steps", [])
    if not steps:
        errors.append(f"Lesson {lesson.get('id')} has no steps")
    if require_v2 and not 8 <= len(steps) <= 10:
        errors.append(f"Lesson {lesson.get('id')} must have 8-10 exercises")
    seen_ids: set[str] = set()
    for step in steps:
        sid = step.get("id")
        if sid in seen_ids:
            errors.append(f"Duplicate step id: {sid}")
        seen_ids.add(sid)
        errors.extend(_validate_step(step, lesson.get("id", "<missing>")))

    if require_v2:
        target = lesson.get("content", {}).get("target") or {}
        context = lesson.get("content", {}).get("context") or {}
        errors.extend(_validate_traditional(target.get("traditional", ""), f"Lesson {lesson.get('id')} target"))
        errors.extend(
            _validate_tone_metadata(target, f"Lesson {lesson.get('id')} target", require_tones=True)
        )
        errors.extend(
            _validate_traditional(context.get("traditional", ""), f"Lesson {lesson.get('id')} context")
        )
        errors.extend(
            f"Lesson {lesson.get('id')} context: {error}"
            for error in validate_jyutping(context.get("jyutping", ""))
        )
        if not validate_jyutping(context.get("jyutping", "")) and context.get(
            "tones"
        ) != _tone_values(context["jyutping"]):
            errors.append(f"Lesson {lesson.get('id')} context tones must exactly match Jyutping")
        learning_steps = [step for step in steps if step.get("type") != "word_intro"]
        if len(learning_steps) >= 2:
            for index, step in enumerate(learning_steps[:2], start=1):
                if step.get("skill") != "listening":
                    errors.append(f"Lesson {lesson.get('id')} step {index} must be listening-first")
                if not step.get("reveal_jyutping") or not step.get("reveal_character"):
                    errors.append(
                        f"Lesson {lesson.get('id')} step {index} must pair Traditional and Jyutping"
                    )
    return errors


def _duplicate_id_errors(items: list[dict], kind: str) -> list[str]:
    ids = [item.get("id") for item in items]
    errors = [f"{kind} missing id" for item_id in ids if not item_id]
    duplicates = sorted(item_id for item_id, count in Counter(ids).items() if item_id and count > 1)
    if duplicates:
        errors.append(f"Duplicate {kind} IDs: {', '.join(duplicates)}")
    return errors


def _validate_prerequisites(
    items: list[dict], kind: str, *, require_previous: bool = False
) -> list[str]:
    errors: list[str] = []
    ids = [item.get("id") for item in items]
    positions = {item_id: index for index, item_id in enumerate(ids)}
    for index, item in enumerate(items):
        item_id = item.get("id")
        prerequisites = item.get("prerequisites", [])
        if len(prerequisites) != len(set(prerequisites)):
            errors.append(f"{kind} {item_id} has duplicate prerequisites")
        for prerequisite in prerequisites:
            if prerequisite not in positions:
                errors.append(f"{kind} {item_id} unknown prerequisite {prerequisite}")
            elif positions[prerequisite] >= index:
                errors.append(f"{kind} {item_id} prerequisite {prerequisite} is not earlier")
        expected = [] if index == 0 else [ids[index - 1]]
        if require_previous and prerequisites != expected:
            errors.append(f"{kind} {item_id} prerequisites must form a single ordered chain")
    return errors


def _validate_v2(doc: dict) -> list[str]:
    errors: list[str] = []
    lessons = doc.get("lessons", [])
    units = doc.get("units", [])
    if len(lessons) != 40:
        errors.append(f"Beginner v2 must contain exactly 40 lessons, found {len(lessons)}")
    lesson_types = Counter(lesson.get("lesson_type") for lesson in lessons)
    if dict(lesson_types) != V2_LESSON_TYPES:
        errors.append(f"Beginner v2 lesson distribution must be {V2_LESSON_TYPES}, found {dict(lesson_types)}")
    skill_counts = Counter(
        step.get("skill")
        for lesson in lessons
        for step in lesson.get("content", {}).get("steps", [])
        if isinstance(step.get("skill"), str)
    )
    if dict(skill_counts) != V2_SKILLS:
        errors.append(f"Beginner v2 skill totals must be {V2_SKILLS}, found {dict(skill_counts)}")
    if any(skill_counts[skill] == 0 for skill in SKILLS):
        errors.append("Every skill must have a nonzero exercise total")
    type_counts = Counter(
        step.get("type") for lesson in lessons for step in lesson.get("content", {}).get("steps", [])
    )
    if dict(type_counts) != V2_EXERCISE_TYPES:
        errors.append(
            f"Beginner v2 exercise type totals must be {V2_EXERCISE_TYPES}, found {dict(type_counts)}"
        )
    exercise_ids = [
        step.get("id") for lesson in lessons for step in lesson.get("content", {}).get("steps", [])
    ]
    if len(exercise_ids) != len(set(exercise_ids)):
        errors.append("Beginner v2 exercise IDs must be globally unique")
    progressions = [
        lesson.get("content", {}).get("context", {}).get("progression") for lesson in lessons
    ]
    if progressions != list(range(1, 41)):
        errors.append("Beginner v2 context progression must be exactly 1 through 40")
    expected_unit_counts = [12, 8, 12, 8]
    actual_unit_counts = [
        sum(lesson.get("unit_id") == unit.get("id") for lesson in lessons) for unit in units
    ]
    if actual_unit_counts != expected_unit_counts:
        errors.append(
            f"Beginner v2 unit lesson counts must be {expected_unit_counts}, found {actual_unit_counts}"
        )
    errors.extend(_validate_prerequisites(lessons, "Lesson", require_previous=True))
    return errors


def validate_seed_document(doc: dict) -> list[str]:
    errors: list[str] = []
    is_v2 = doc.get("version") == "2.0.0"
    lexemes = doc.get("lexemes", [])
    characters = doc.get("characters", [])
    lessons = doc.get("lessons", [])
    units = doc.get("units", [])
    stories = doc.get("stories", [])
    for collection, kind in (
        (units, "unit"),
        (lessons, "lesson"),
        (lexemes, "lexeme"),
        (characters, "character"),
        (stories, "story"),
    ):
        errors.extend(_duplicate_id_errors(collection, kind))
    for lex in lexemes:
        errors.extend(validate_lexeme(lex))
        if is_v2:
            errors.extend(_validate_traditional(lex.get("traditional", ""), f"Lexeme {lex.get('id')}"))
            errors.extend(
                _validate_tone_metadata(lex, f"Lexeme {lex.get('id')}", require_tones=True)
            )
    for character in characters:
        if is_v2:
            errors.extend(_validate_traditional(character.get("glyph", ""), f"Character {character.get('id')}"))
            errors.extend(
                _validate_tone_metadata(
                    character, f"Character {character.get('id')}", require_tones=True
                )
            )
    unit_ids = {unit.get("id") for unit in units}
    lexeme_ids = {lexeme.get("id") for lexeme in lexemes}
    for lesson in lessons:
        errors.extend(validate_lesson(lesson, require_v2=is_v2))
        if lesson.get("unit_id") not in unit_ids:
            errors.append(f"Lesson {lesson.get('id')} references unknown unit")
        for vocabulary in lesson.get("content", {}).get("vocabulary", []):
            if vocabulary.get("lexeme_id") not in lexeme_ids:
                errors.append(
                    f"Lesson {lesson.get('id')} references unknown lexeme {vocabulary.get('lexeme_id')}"
                )
    errors.extend(_validate_prerequisites(units, "Unit", require_previous=is_v2))
    if is_v2:
        errors.extend(_validate_v2(doc))
    return errors
