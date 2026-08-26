"""Tests for the cantonese.ai TTS gateway."""

import httpx
import pytest

from app.core.config import Settings
from app.services.tts import CantoneseAiTTSGateway, audio_content_hash


@pytest.mark.asyncio
async def test_cantonese_ai_gateway_uses_gigi_and_account_default_model():
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(__import__("json").loads(request.content))
        return httpx.Response(200, content=b"RIFF-test-audio")

    settings = Settings(
        _env_file=None,
        cantonese_ai_api_key="test-key",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = CantoneseAiTTSGateway(settings=settings, client=client)
        audio = await gateway.generate_audio("水", jyutping="seoi2")

    assert audio == b"RIFF-test-audio"
    assert captured["api_key"] == "test-key"
    assert "model_id" not in captured
    assert captured["voice_id"] == "50a9a698-1f99-437c-a07d-9cad435c5f8a"
    assert captured["jyutping"] == "seoi2"
    assert captured["output_extension"] == "wav"


@pytest.mark.asyncio
async def test_cantonese_ai_gateway_skips_without_api_key():
    gateway = CantoneseAiTTSGateway(settings=Settings(_env_file=None))
    assert await gateway.generate_audio("水") is None


def test_cantonese_ai_audio_hash_is_stable():
    first = audio_content_hash("水", "gigi", "v6")
    assert first == audio_content_hash("水", "gigi", "v6")
    assert first != audio_content_hash("水", "other", "v6")
