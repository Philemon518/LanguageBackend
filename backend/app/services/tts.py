"""Reusable text-to-speech gateway for curriculum audio."""

import hashlib
import logging

import httpx

from ..core.config import Settings, get_settings

logger = logging.getLogger("canto.tts")
AUDIO_GENERATION_VERSION = "cantonese-ai-v6"


def audio_content_hash(text: str, voice: str, model: str) -> str:
    """Return the stable cache key used for generated curriculum audio."""
    payload = f"{text}|{voice}|{model}|wav|{AUDIO_GENERATION_VERSION}"
    return hashlib.sha256(payload.encode()).hexdigest()


class CantoneseAiTTSGateway:
    """Small async client for cantonese.ai's direct audio TTS endpoint."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client

    async def generate_audio(
        self,
        text: str,
        *,
        jyutping: str | None = None,
        model_id: str | None = None,
        voice_id: str | None = None,
    ) -> bytes | None:
        """Synthesize Cantonese text as a 24 kHz WAV file."""
        if not self.settings.cantonese_ai_api_key:
            logger.warning("No CANTONESE_AI_API_KEY — skipping TTS generation")
            return None
        if not text.strip() and not (jyutping or "").strip():
            raise ValueError("Text or Jyutping is required for TTS")

        payload = {
            "api_key": self.settings.cantonese_ai_api_key,
            "text": text,
            "frame_rate": "24000",
            "speed": 1,
            "pitch": 0,
            "language": "cantonese",
            "output_extension": "wav",
            "voice_id": voice_id or self.settings.cantonese_ai_voice_id,
            "should_return_timestamp": False,
        }
        # The current API selects the subscribed account's TTS model. Although
        # the public docs advertise model_id="v6", the live endpoint rejects
        # that value while accepting Jyutping with the account default.
        if jyutping:
            payload["jyutping"] = jyutping

        if self.client is not None:
            response = await self.client.post(
                self.settings.cantonese_ai_tts_url,
                json=payload,
            )
        else:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    self.settings.cantonese_ai_tts_url,
                    json=payload,
                )
        if response.is_error:
            detail = response.text[:500]
            raise httpx.HTTPStatusError(
                f"cantonese.ai TTS failed ({response.status_code}): {detail}",
                request=response.request,
                response=response,
            )
        return response.content

    async def generate_tts_bytes(
        self,
        text: str,
        *,
        jyutping: str | None = None,
        model_id: str | None = None,
        voice_id: str | None = None,
    ) -> bytes | None:
        """Compatibility name for callers that cache raw synthesized bytes."""
        return await self.generate_audio(
            text,
            jyutping=jyutping,
            model_id=model_id,
            voice_id=voice_id,
        )
