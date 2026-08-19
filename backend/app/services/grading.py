"""Exercise grading and feedback."""

from ..models.schemas import ExerciseStep, WritingFeedback


def grade_exercise(step: ExerciseStep, response: dict) -> tuple[bool, float, str | None]:
    ex_type = step.type
    if ex_type in (
        "select_tone",
        "select_meaning",
        "select_jyutping",
        "select_character",
        "match",
        "word_intro",
    ):
        selected = response.get("selected_option_id")
        correct = selected == step.correct_option_id
        return correct, 1.0 if correct else 0.0, None if correct else step.hint

    if ex_type == "order_words":
        order = response.get("order", [])
        expected = step.metadata.get("expected_order", [])
        correct = order == expected
        return correct, 1.0 if correct else 0.3, None if correct else "Check word order."

    if ex_type == "cloze":
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
            expected_text
            or step.metadata.get("expected")
            or step.reveal_jyutping
            or ""
        ).strip()
        if not transcript:
            return False, 0.0, "No speech detected. Try again."
        if expected_text and (
            expected_text in transcript or transcript in expected_text
        ):
            return True, 1.0, "Clear match. Listen once more and compare your tone."
        # Conservative: partial match on jyutping syllables
        exp_parts = expected.lower().split()
        got_parts = transcript.lower().split()
        overlap = len(set(exp_parts) & set(got_parts))
        score = min(1.0, overlap / max(len(exp_parts), 1))
        correct = score >= 0.7
        feedback = None if correct else "Focus on tone and syllable shape. Listen again, then retry."
        return correct, score, feedback

    if ex_type == "write_sentence":
        text = (response.get("text") or "").strip()
        return grade_writing(
            text,
            step.metadata.get("expected_patterns", []),
            step.metadata.get("target_vocab", []),
        )

    return False, 0.0, "Unknown exercise type"


def grade_writing(text: str, patterns: list[str], vocab: list[str]) -> tuple[bool, float, str | None]:
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
        feedback="Good use of vocabulary." if acceptable else "Include more target words and patterns.",
        matched_vocab=matched_vocab,
        matched_patterns=matched_patterns,
    )
    return acceptable, score, feedback.feedback
