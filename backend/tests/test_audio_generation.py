"""Tests for strict curriculum audio QA helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from content.scripts.generate_audio import (
    normalize_cantonese_transcript,
    resample_pcm16,
    transcripts_match,
)


def test_transcript_normalization_ignores_formatting_not_extra_particles():
    assert normalize_cantonese_transcript("我飲水。") == "我飲水"
    assert normalize_cantonese_transcript(" 我 飲 水 ") == "我飲水"
    assert normalize_cantonese_transcript("我飲水啊") != "我飲水"


def test_single_syllable_transcripts_allow_asr_particles():
    assert transcripts_match("史", "史仔。")
    assert transcripts_match("事", "好事。")
    assert transcripts_match("五", "嗯。")
    assert not transcripts_match("我飲水", "我飲水啊")


def test_pcm_resampler_converts_24khz_to_16khz():
    one_second_silence = b"\x00\x00" * 24_000
    result = resample_pcm16(one_second_silence)
    assert len(result) == 16_000 * 2
