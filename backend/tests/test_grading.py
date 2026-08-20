"""Test exercise grading."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.schemas import ExerciseStep
from app.services.grading import grade_exercise, grade_writing


def test_select_tone_correct():
    step = ExerciseStep(
        id="t1",
        type="select_tone",
        skill="listening",
        prompt="Tone?",
        correct_option_id="t2",
    )
    correct, score, _ = grade_exercise(step, {"selected_option_id": "t2"})
    assert correct and score == 1.0


def test_select_tone_wrong():
    step = ExerciseStep(
        id="t1",
        type="select_tone",
        skill="listening",
        prompt="Tone?",
        correct_option_id="t2",
        hint="Listen for rising tone",
    )
    correct, score, feedback = grade_exercise(step, {"selected_option_id": "t1"})
    assert not correct and score == 0.0
    assert feedback == "Listen for rising tone"


def test_order_words():
    step = ExerciseStep(
        id="o1",
        type="order_words",
        skill="writing",
        prompt="Order",
        metadata={"expected_order": ["w1", "w2", "w3"]},
    )
    correct, score, _ = grade_exercise(step, {"order": ["w1", "w2", "w3"]})
    assert correct and score == 1.0


def test_cloze_accepts_word_choice_or_optional_manual_typing():
    step = ExerciseStep(
        id="c1",
        type="cloze",
        skill="writing",
        prompt="Complete",
        correct_option_id="answer",
        metadata={"expected": "水", "allow_manual_input": True},
    )

    selected, _, _ = grade_exercise(step, {"selected_option_id": "answer"})
    typed, _, _ = grade_exercise(step, {"answer": "水"})

    assert selected
    assert typed


def test_writing_feedback():
    ok, score, _msg = grade_writing("我食蘋果。", ["我食蘋果"], ["我", "食", "蘋果"])
    assert ok and score >= 0.5


def test_speaking_rejects_english_transcript():
    step = ExerciseStep(
        id="speak-1",
        type="speak",
        skill="speaking",
        prompt="Say water",
        metadata={"expected": "seoi2", "expected_text": "水"},
    )
    correct, score, feedback = grade_exercise(step, {"transcript": "water"})
    assert not correct
    assert score == 0.0
    assert feedback == "We heard English. Try again in Cantonese."


def test_speaking_accepts_matching_cantonese_transcript():
    step = ExerciseStep(
        id="speak-1",
        type="speak",
        skill="speaking",
        prompt="Say water",
        metadata={"expected": "seoi2", "expected_text": "水"},
    )
    correct, score, feedback = grade_exercise(step, {"transcript": "水"})
    assert correct
    assert score == 1.0
    assert feedback
