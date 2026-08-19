"""Test Qwen utilities."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.qwen import QwenRealtimeGateway, audio_content_hash


def test_content_hash_stable():
    h1 = audio_content_hash("水", "Kiki", "qwen3.5-omni-plus-realtime")
    h2 = audio_content_hash("水", "Kiki", "qwen3.5-omni-plus-realtime")
    assert h1 == h2


def test_instructions_include_vocab():
    gw = QwenRealtimeGateway()
    text = gw.build_instructions("Ordering food", ["食", "飲"], ["我要..."], "beginner")
    assert "Cantonese" in text
    assert "食" in text
