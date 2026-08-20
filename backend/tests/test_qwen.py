"""Test Qwen utilities."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.qwen import QwenRealtimeGateway, audio_content_hash, pcm16_to_wav


def test_content_hash_stable():
    h1 = audio_content_hash("水", "Kiki", "qwen3.5-omni-plus-realtime")
    h2 = audio_content_hash("水", "Kiki", "qwen3.5-omni-plus-realtime")
    assert h1 == h2


def test_instructions_include_vocab():
    gw = QwenRealtimeGateway()
    text = gw.build_instructions("Ordering food", ["食", "飲"], ["我要..."], "beginner")
    assert "Cantonese" in text
    assert "食" in text


def test_pcm16_to_wav_default_sample_rate():
    wav_bytes = pcm16_to_wav(b"\x00\x00" * 100)
    assert wav_bytes.startswith(b"RIFF")


@pytest.mark.asyncio
async def test_connect_session_locks_cantonese_transcription():
    gw = QwenRealtimeGateway()
    sent_payloads: list[dict] = []

    class FakeWebSocket:
        async def send(self, payload: str) -> None:
            sent_payloads.append(json.loads(payload))

    with patch("app.services.qwen.websockets.connect", new=AsyncMock(return_value=FakeWebSocket())):
        await gw.connect_session("Practice Cantonese", AsyncMock())

    session_update = sent_payloads[0]["session"]
    assert session_update["input_audio_transcription"] == {
        "model": "qwen3-asr-flash",
        "language": "yue",
    }
