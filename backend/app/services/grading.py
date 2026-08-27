"""Exercise grading and feedback."""

from ..models.schemas import ExerciseStep, WritingFeedback

INTRO_STEP_TYPES = {"lesson_intro", "word_intro"}
CHOICE_STEP_TYPES = {
    "choice",
    "multiple_choice",
    "image",
    "audio",
    "image_choice",
    "audio_choice",
}
COMPARISON_STEP_TYPES = {
    "image_comparison",
    "audio_comparison",
    "image_compare",
    "audio_compare",
    "compare_images",
    "compare_audio",
}


def is_intro_step_type(step_type: str) -> bool:
    return step_type in INTRO_STEP_TYPES or step_type.endswith("_intro")


def is_intro_step(step: ExerciseStep) -> bool:
    return is_intro_step_type(step.type)


def _step_identity(step: ExerciseStep | dict) -> tuple[str, str]:
    if isinstance(step, dict):
        return str(step.get("id") or ""), str(step.get("type") or "")
    return step.id, step.type


def required_step_ids(steps: list[ExerciseStep | dict]) -> list[str]:
    ids: list[str] = []
    for step in steps:
        step_id, step_type = _step_identity(step)
        if step_id and not is_intro_step_type(step_type):
            ids.append(step_id)
    return ids


def lesson_is_complete(steps: list[ExerciseStep | dict], correct_ids: set[str]) -> bool:
    required = required_step_ids(steps)
    if required:
        return all(step_id in correct_ids for step_id in required)
    return bool(steps) and all(_step_identity(step)[0] in correct_ids for step in steps)


def first_incomplete_index(steps: list[ExerciseStep | dict], correct_ids: set[str]) -> int:
    if lesson_is_complete(steps, correct_ids):
        return len(steps)
    return next(
        (
            index
            for index, step in enumerate(steps)
            if _step_identity(step)[0] not in correct_ids
        ),
        len(steps),
    )


def _looks_like_english(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    cjk = sum(1 for ch in stripped if "\u4e00" <= ch <= "\u9fff")
    ascii_letters = sum(1 for ch in stripped if ch.isascii() and ch.isalpha())
    return ascii_letters > 0 and cjk == 0


def grade_exercise(step: ExerciseStep, response: dict) -> tuple[bool, float, str | None]:
    ex_type = step.type
    if is_intro_step(step):
        return True, 1.0, None

    if (
        ex_type
        in (
            "select_tone",
            "select_meaning",
            "select_jyutping",
            "select_character",
            "match",
        )
        or ex_type in CHOICE_STEP_TYPES
    ):
        selected = (
            response.get("selected_option_id")
            or response.get("selected_id")
            or response.get("choice_id")
            or response.get("selected")
        )
        expected = step.correct_option_id or step.metadata.get("correct_option_id")
        correct = selected == expected
        return correct, 1.0 if correct else 0.0, None if correct else step.hint

    if ex_type == "comparison" or ex_type in COMPARISON_STEP_TYPES:
        selected_ids = response.get("selected_option_ids")
        expected_ids = step.metadata.get("expected_option_ids") or (step.model_extra or {}).get(
            "correct_option_ids"
        )
        if selected_ids is not None and expected_ids is not None:
            correct = selected_ids == expected_ids
        else:
            selected = (
                response.get("selected_option_id")
                or response.get("selected_id")
                or response.get("selected")
            )
            expected = step.correct_option_id or step.metadata.get("correct_option_id")
            correct = selected == expected
        return correct, 1.0 if correct else 0.0, None if correct else step.hint

    if ex_type in {"typing", "type_answer"}:
        answer = str(response.get("text") or response.get("answer") or "").strip()
        accepted = step.metadata.get("accepted_answers")
        if accepted is None:
            extra = step.model_extra or {}
            accepted = extra.get("accepted_answers") or extra.get("correct_answer")
        if not isinstance(accepted, list):
            accepted = [
                accepted
                or step.metadata.get("expected")
                or step.reveal_character
                or step.reveal_jyutping
                or ""
            ]
        correct = answer.casefold() in {str(candidate).strip().casefold() for candidate in accepted}
        return correct, 1.0 if correct else 0.0, None if correct else step.hint

    if ex_type == "order_words":
        order = response.get("order", [])
        expected = step.metadata.get("expected_order", [])
        correct = order == expected
        return correct, 1.0 if correct else 0.3, None if correct else "Check word order."

    if ex_type == "cloze":
        selected = response.get("selected_option_id")
        if selected is not None:
            correct = selected == step.correct_option_id
            return correct, 1.0 if correct else 0.0, None if correct else step.hint

        answer = (response.get("answer") or "").strip()
        expected = (step.metadata.get("expected") or "").strip()
        correct = answer == expected
        return correct, 1.0 if correct else 0.0, None if correct else step.hint

    if ex_type == "dictation":
        answer = (response.get("text") or "").strip()
        expected = (step.metadata.get("expected") or step.reveal_jyutping or "").strip()
        correct = answer.lower() == expected.lower()
        return correct, 1.0 if correct else 0.2, None if correct else f"Expected: {expected}"

    if ex_type == "speak":
        transcript = (response.get("transcript") or "").strip()
        expected_text = (step.metadata.get("expected_text") or "").strip()
        expected = (
            expected_text or step.metadata.get("expected") or step.reveal_jyutping or ""
        ).strip()
        if not transcript:
            return False, 0.0, "No speech detected. Try again."
        if _looks_like_english(transcript):
            return False, 0.0, "We heard English. Try again in Cantonese."
        if expected_text and (expected_text in transcript or transcript in expected_text):
            return True, 1.0, "Clear match. Listen once more and compare your tone."
        # Conservative: partial match on jyutping syllables
        exp_parts = expected.lower().split()
        got_parts = transcript.lower().split()
        overlap = len(set(exp_parts) & set(got_parts))
        score = min(1.0, overlap / max(len(exp_parts), 1))
        correct = score >= 0.7
        feedback = (
            None if correct else "Focus on tone and syllable shape. Listen again, then retry."
        )
        return correct, score, feedback

    if ex_type == "write_sentence":
        text = (response.get("text") or "").strip()
        return grade_writing(
            text,
            step.metadata.get("expected_patterns", []),
            step.metadata.get("target_vocab", []),
        )

    return False, 0.0, "Unknown exercise type"


def grade_writing(
    text: str, patterns: list[str], vocab: list[str]
) -> tuple[bool, float, str | None]:
    if not text:
        return False, 0.0, "Write a sentence using the target vocabulary."
    matched_vocab = [v for v in vocab if v in text]
    matched_patterns = [p for p in patterns if p.replace(" ", "") in text.replace(" ", "")]
    score = (len(matched_vocab) / max(len(vocab), 1)) * 0.6 + (
        len(matched_patterns) / max(len(patterns), 1)
    ) * 0.4
    acceptable = score >= 0.5 and len(matched_vocab) >= 1
    feedback = WritingFeedback(
        acceptable=acceptable,
        feedback="Good use of vocabulary."
        if acceptable
        else "Include more target words and patterns.",
        matched_vocab=matched_vocab,
        matched_patterns=matched_patterns,
    )
    return acceptable, score, feedback.feedback
