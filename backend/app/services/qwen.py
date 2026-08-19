"""Qwen / DashScope speech gateway."""

import asyncio
import base64
import hashlib
import json
import logging
from typing import Any, Callable

import httpx
import websockets

from ..core.config import get_settings

logger = logging.getLogger("canto.qwen")
settings = get_settings()


def audio_content_hash(text: str, voice: str, model: str) -> str:
    payload = f"{text}|{voice}|{model}|pcm16"
    return hashlib.sha256(payload.encode()).hexdigest()


class QwenRealtimeGateway:
    """WebSocket proxy to Qwen Omni Realtime for Cantonese conversation."""

    def __init__(self) -> None:
        self.model = settings.qwen_realtime_model
        self.voice = settings.qwen_tts_voice
        self.api_key = settings.dashscope_api_key
        self.url = f"{settings.qwen_realtime_url}?model={self.model}"

    def build_instructions(
        self,
        scenario: str,
        target_vocab: list[str],
        grammar_limits: list[str],
        level: str = "beginner",
    ) -> str:
        vocab_str = ", ".join(target_vocab) if target_vocab else "basic greetings"
        grammar_str = ", ".join(grammar_limits) if grammar_limits else "present aspect, 唔 negation"
        return (
            f"You are a friendly Cantonese tutor in Hong Kong. Speak ONLY in Cantonese (粵語). "
            f"Scenario: {scenario}. Learner level: {level}. "
            f"Encourage the learner to use these words naturally: {vocab_str}. "
            f"Grammar scope: {grammar_str}. "
            f"Keep replies short (1-2 sentences). Speak clearly with correct tones. "
            f"If the learner uses English, gently reply in Cantonese and model the phrase."
        )

    async def connect_session(
        self,
        instructions: str,
        on_event: Callable[[dict[str, Any]], Any],
    ) -> websockets.WebSocketClientProtocol:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        ws = await websockets.connect(self.url, additional_headers=headers)
        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "voice": self.voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "instructions": instructions,
                "turn_detection": {"type": "semantic_vad"},
            },
        }
        await ws.send(json.dumps(session_update))

        async def reader() -> None:
            try:
                async for message in ws:
                    event = json.loads(message)
                    await on_event(event)
            except websockets.ConnectionClosed:
                logger.info("Qwen WebSocket closed")

        asyncio.create_task(reader())
        return ws

    async def send_audio(self, ws: websockets.WebSocketClientProtocol, pcm_bytes: bytes) -> None:
        encoded = base64.b64encode(pcm_bytes).decode()
        await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": encoded}))

    async def generate_tts_bytes(self, text: str, voice: str | None = None) -> bytes | None:
        """Batch TTS via realtime model single-turn (for cached curriculum audio)."""
        if not self.api_key:
            logger.warning("No DASHSCOPE_API_KEY — skipping TTS generation")
            return None
        voice = voice or self.voice
        collected: list[bytes] = []
        done = asyncio.Event()

        async def on_event(event: dict[str, Any]) -> None:
            if event.get("type") == "response.audio.delta":
                collected.append(base64.b64decode(event["delta"]))
            elif event.get("type") == "response.done":
                done.set()

        ws = await self.connect_session(
            instructions=f"Say exactly this in Cantonese, nothing else: {text}",
            on_event=on_event,
        )
        # Trigger response with text
        await ws.send(
            json.dumps(
                {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": text}],
                    },
                }
            )
        )
        await ws.send(json.dumps({"type": "response.create"}))
        try:
            await asyncio.wait_for(done.wait(), timeout=30)
        except asyncio.TimeoutError:
            logger.error("TTS generation timed out for: %s", text[:50])
        finally:
            await ws.close()
        return b"".join(collected) if collected else None


async def transcribe_cantonese(audio_bytes: bytes) -> str | None:
    """Transcribe one PCM16/16 kHz Cantonese utterance through Qwen Realtime."""
    if not settings.dashscope_api_key:
        return None
    url = f"{settings.qwen_realtime_url}?model={settings.qwen_realtime_model}"
    headers = {"Authorization": f"Bearer {settings.dashscope_api_key}"}
    transcript: str | None = None
    async with websockets.connect(url, additional_headers=headers) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "session.update",
                    "session": {
                        "modalities": ["text"],
                        "input_audio_format": "pcm16",
                        "instructions": (
                            "Transcribe the learner's Cantonese exactly. "
                            "Do not translate or correct it."
                        ),
                        "turn_detection": None,
                    },
                }
            )
        )
        chunk_size = 16_000
        for start in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[start : start + chunk_size]
            await ws.send(
                json.dumps(
                    {
                        "type": "input_audio_buffer.append",
                        "audio": base64.b64encode(chunk).decode(),
                    }
                )
            )
        await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        await ws.send(json.dumps({"type": "response.create"}))

        try:
            async with asyncio.timeout(20):
                async for raw in ws:
                    event = json.loads(raw)
                    if event.get("type") == "conversation.item.input_audio_transcription.completed":
                        transcript = event.get("transcript")
                    elif event.get("type") == "response.done":
                        break
        except TimeoutError:
            logger.warning("Cantonese transcription timed out")
    return transcript
