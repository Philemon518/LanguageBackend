"""Test Cantonese speech assessment."""

import io
import sys
import wave
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import qwen
from app.services.qwen import pcm16_to_wav, transcribe_cantonese_asr


def test_pcm16_to_wav_wraps_16khz_mono_audio():
    pcm = b"\x00\x01" * 8000
    wav_bytes = pcm16_to_wav(pcm, sample_rate=16000)

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 8000


@pytest.mark.asyncio
async def test_transcribe_cantonese_asr_uses_yue_language():
    pcm = b"\x00\x00" * 1600
    wav_bytes = pcm16_to_wav(pcm)

    with (
        patch.object(qwen.settings, "dashscope_api_key", "test-key"),
        patch("dashscope.MultiModalConversation.call") as mock_call,
    ):
        mock_call.return_value.status_code = 200
        mock_call.return_value.output = {
            "choices": [{"message": {"content": [{"text": "水"}]}}]
        }
        transcript = await transcribe_cantonese_asr(wav_bytes, expected_text="水")

    assert transcript == "水"
    _, kwargs = mock_call.call_args
    assert kwargs["model"] == "qwen3-asr-flash"
    assert kwargs["asr_options"] == {"language": "yue", "enable_itn": False}


@pytest.mark.asyncio
async def test_assess_drill_routes_through_cantonese_asr():
    from app.api.speech import assess_drill

    pcm = b"\x00\x00" * 1600
    mock_upload = AsyncMock()
    mock_upload.read = AsyncMock(return_value=pcm)

    with patch(
        "app.api.speech.transcribe_cantonese_asr",
        new=AsyncMock(return_value="水"),
    ) as mock_asr:
        result = await assess_drill(
            audio=mock_upload,
            expected_text="水",
            user=type("User", (), {"id": "user-1"})(),
            expected_jyutping="seoi2",
        )

    assert result["transcript"] == "水"
    assert result["expected_text"] == "水"
    mock_asr.assert_awaited_once()
    wav_bytes, kwargs = mock_asr.await_args.args[0], mock_asr.await_args.kwargs
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getframerate() == 16000
    assert kwargs["expected_text"] == "水"
