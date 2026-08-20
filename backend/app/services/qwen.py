"""Qwen / DashScope speech gateway."""

import asyncio
import base64
import hashlib
import json
import logging
import tempfile
import threading
import uuid
from collections.abc import Callable
from typing import Any

import websockets

from ..core.config import get_settings

logger = logging.getLogger("canto.qwen")
settings = get_settings()
AUDIO_GENERATION_VERSION = "hk-cantonese-strict-v3"


def audio_content_hash(text: str, voice: str, model: str) -> str:
    payload = f"{text}|{voice}|{model}|pcm16|{AUDIO_GENERATION_VERSION}"
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
        self.voice = voice
        collected: list[bytes] = []
        done = asyncio.Event()
        failure: list[str] = []

        async def on_event(event: dict[str, Any]) -> None:
            if event.get("type") == "response.audio.delta":
                collected.append(base64.b64decode(event["delta"]))
            elif event.get("type") == "response.done":
                done.set()
            elif event.get("type") in {"error", "response.failed"}:
                failure.append(json.dumps(event, ensure_ascii=False))
                done.set()

        ws = await self.connect_session(
            instructions=(
                "You are recording one clean pronunciation clip for a Hong Kong "
                "Cantonese course. Use natural Hong Kong Cantonese pronunciation "
                "and accurate tones. Speak the target text exactly once and nothing "
                "else. Start immediately and stop immediately after the target. "
                "Never translate, explain, introduce, repeat, or append any sound, "
                "word, filler, or sentence-final particle. In particular, do not add "
                "啊, 呀, 喎, 啦, 囉, or any English words. Do not speak punctuation. "
                f"The complete target text is: {text}"
            ),
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
        except TimeoutError:
            logger.error("TTS generation timed out for: %s", text[:50])
        finally:
            await ws.close()
        if failure:
            logger.error("TTS failed for %r using voice %s: %s", text, voice, failure[-1])
        return b"".join(collected) if collected else None

    async def generate_cosyvoice_bytes(
        self,
        text: str,
        *,
        voice: str = "longanyue_v3",
        model: str = "cosyvoice-v3-flash",
    ) -> bytes | None:
        """Synthesize exact text with Alibaba's dedicated Cantonese TTS service."""
        if not self.api_key:
            logger.warning("No DASHSCOPE_API_KEY — skipping TTS generation")
            return None

        task_id = str(uuid.uuid4())
        inference_url = settings.qwen_realtime_url.rsplit("/", 1)[0] + "/inference"
        headers = {
            "Authorization": f"bearer {self.api_key}",
            "X-DashScope-DataInspection": "enable",
        }
        collected: list[bytes] = []
        async with websockets.connect(
            inference_url, additional_headers=headers, max_size=None
        ) as ws:
            await ws.send(
                json.dumps(
                    {
                        "header": {
                            "action": "run-task",
                            "task_id": task_id,
                            "streaming": "duplex",
                        },
                        "payload": {
                            "task_group": "audio",
                            "task": "tts",
                            "function": "SpeechSynthesizer",
                            "model": model,
                            "parameters": {
                                "text_type": "PlainText",
                                "voice": voice,
                                "format": "pcm",
                                "sample_rate": 24_000,
                                "volume": 50,
                                "rate": 1,
                                "pitch": 1,
                                "enable_ssml": False,
                            },
                            "input": {},
                        },
                    }
                )
            )

            async with asyncio.timeout(30):
                async for message in ws:
                    if isinstance(message, bytes):
                        collected.append(message)
                        continue

                    event = json.loads(message)
                    header = event.get("header", {})
                    event_type = header.get("event")
                    if event_type == "task-started":
                        await ws.send(
                            json.dumps(
                                {
                                    "header": {
                                        "action": "continue-task",
                                        "task_id": task_id,
                                        "streaming": "duplex",
                                    },
                                    "payload": {"input": {"text": text}},
                                }
                            )
                        )
                        await asyncio.sleep(0.1)
                        await ws.send(
                            json.dumps(
                                {
                                    "header": {
                                        "action": "finish-task",
                                        "task_id": task_id,
                                        "streaming": "duplex",
                                    },
                                    "payload": {"input": {}},
                                }
                            )
                        )
                    elif event_type == "task-finished":
                        break
                    elif event_type == "task-failed":
                        raise RuntimeError(
                            header.get("error_message") or "CosyVoice task failed"
                        )

        return b"".join(collected) if collected else None

    async def generate_hk_cantonese_bytes(
        self,
        text: str,
        *,
        voice: str = "Kiki",
        model: str = "qwen3-tts-flash-realtime",
    ) -> bytes | None:
        """Generate exact text with Qwen's native Hong Kong Cantonese voice."""
        if not self.api_key:
            logger.warning("No DASHSCOPE_API_KEY — skipping TTS generation")
            return None

        def synthesize() -> bytes:
            import dashscope
            from dashscope.audio.qwen_tts_realtime import (
                AudioFormat,
                QwenTtsRealtime,
                QwenTtsRealtimeCallback,
            )

            class AudioCollector(QwenTtsRealtimeCallback):
                def __init__(self) -> None:
                    self.audio: list[bytes] = []
                    self.done = threading.Event()
                    self.error: str | None = None

                def on_open(self) -> None:
                    return

                def on_close(self, code, message) -> None:
                    if code:
                        self.error = f"{code}: {message}"
                    self.done.set()

                def on_event(self, response) -> None:
                    event_type = response.get("type")
                    if event_type == "response.audio.delta":
                        self.audio.append(base64.b64decode(response["delta"]))
                    elif event_type == "response.done":
                        self.done.set()
                    elif event_type == "error":
                        self.error = str(response)
                        self.done.set()

            dashscope.api_key = self.api_key
            collector = AudioCollector()
            synthesizer = QwenTtsRealtime(
                model=model,
                callback=collector,
                url=settings.qwen_realtime_url,
            )
            synthesizer.connect()
            synthesizer.update_session(
                voice=voice,
                response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
                mode="server_commit",
                language_type="Chinese",
            )
            synthesizer.append_text(text)
            synthesizer.finish()
            if not collector.done.wait(timeout=20):
                synthesizer.close()
                raise TimeoutError(f"TTS timed out for {text!r}")
            synthesizer.close()
            if collector.error:
                raise RuntimeError(f"TTS failed for {text!r}: {collector.error}")
            return b"".join(collector.audio)

        return await asyncio.to_thread(synthesize)


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
                            "Transcribe the Cantonese audio exactly in Traditional "
                            "Chinese. Preserve every spoken word and particle. "
                            "Do not translate, correct, explain, or add text."
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


async def transcribe_cantonese_asr(
    wav_bytes: bytes, expected_text: str | None = None
) -> str | None:
    """Transcribe a WAV clip with Qwen's Cantonese-specific ASR model."""
    if not settings.dashscope_api_key:
        return None

    def recognize() -> str | None:
        import dashscope

        dashscope.api_key = settings.dashscope_api_key
        dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            audio_file.write(wav_bytes)
            audio_file.flush()
            messages: list[dict] = []
            if expected_text:
                messages.append(
                    {
                        "role": "system",
                        "content": [
                            {
                                "text": (
                                    "Validate a Hong Kong Cantonese course "
                                    "recording. The expected exact text is: "
                                    f"{expected_text}. Transcribe every spoken "
                                    "word and particle verbatim in Traditional "
                                    "Chinese. Do not force the expected text if "
                                    "the audio differs, and do not explain."
                                )
                            }
                        ],
                    }
                )
            messages.append(
                {
                    "role": "user",
                    "content": [{"audio": audio_file.name}],
                }
            )
            result = dashscope.MultiModalConversation.call(
                api_key=settings.dashscope_api_key,
                model="qwen3-asr-flash",
                messages=messages,
                result_format="message",
                asr_options={"language": "yue", "enable_itn": False},
            )
        if result.status_code != 200:
            raise RuntimeError(f"Qwen Cantonese STT failed: {result.message}")
        choices = result.output.get("choices") or []
        if not choices:
            return None
        content = choices[0]["message"].get("content") or []
        return "".join(part.get("text", "") for part in content)

    return await asyncio.to_thread(recognize)
