"""Generate and cache curriculum audio via Qwen TTS."""

import argparse
import asyncio
import io
import json
import struct
import sys
import unicodedata
import wave
from datetime import UTC, datetime
from pathlib import Path

from opencc import OpenCC

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.models.orm import CurriculumVersion, Lesson, MediaAsset, Unit
from app.services.qwen import (
    QwenRealtimeGateway,
    audio_content_hash,
    transcribe_cantonese_asr,
)
from app.services.storage import upload_curriculum_audio


def pcm_to_wav(pcm: bytes, sample_rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


MANIFEST_PATH = ROOT / "backend" / "local_data" / "audio" / "manifest.json"
AUDIO_DIR = MANIFEST_PATH.parent / "beginner"
S2T_CONVERTER = OpenCC("s2t")
COSYVOICE_FALLBACK_VOICE = "longanyue_v3"
COSYVOICE_FALLBACK_MODEL = "cosyvoice-v3-flash"
COSYVOICE_PRONUNCIATION_TEXT = {"語": "雨"}


async def collect_texts() -> list[str]:
    texts: list[str] = []
    async with SessionLocal() as db:
        version_result = await db.execute(
            select(CurriculumVersion)
            .where(CurriculumVersion.level == "beginner")
            .order_by(CurriculumVersion.created_at.desc())
            .limit(1)
        )
        version = version_result.scalar_one_or_none()
        if version is None:
            return []
        result = await db.execute(
            select(Lesson).join(Unit, Lesson.unit_id == Unit.id).where(
                Unit.curriculum_version_id == version.id
            )
        )
        for lesson in result.scalars().all():
            for step in (lesson.content_json or {}).get("steps", []):
                audio = step.get("audio") or {}
                text = audio.get("text")
                if text:
                    texts.append(text)
                for option in step.get("options", []):
                    option_text = (option.get("audio") or {}).get("text")
                    if option_text:
                        texts.append(option_text)
    return list(dict.fromkeys(texts))


def inspect_wav(data: bytes) -> tuple[bool, float]:
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            duration = wav.getnframes() / max(wav.getframerate(), 1)
            valid = (
                wav.getnchannels() == 1
                and wav.getsampwidth() == 2
                and duration >= 0.08
            )
            return valid, duration
    except (wave.Error, EOFError):
        return False, 0.0


def normalize_cantonese_transcript(text: str) -> str:
    """Normalize formatting while preserving every spoken character/particle."""
    normalized = S2T_CONVERTER.convert(
        unicodedata.normalize("NFKC", text).strip()
    )
    return "".join(
        char
        for char in normalized
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def resample_pcm16(
    pcm: bytes, source_rate: int = 24_000, target_rate: int = 16_000
) -> bytes:
    """Linearly resample mono little-endian PCM16 for the STT endpoint."""
    if source_rate == target_rate or len(pcm) < 4:
        return pcm
    sample_count = len(pcm) // 2
    samples = struct.unpack(f"<{sample_count}h", pcm[: sample_count * 2])
    output_count = max(1, round(sample_count * target_rate / source_rate))
    output: list[int] = []
    for index in range(output_count):
        position = index * source_rate / target_rate
        left = min(int(position), sample_count - 1)
        right = min(left + 1, sample_count - 1)
        fraction = position - left
        value = round(samples[left] * (1 - fraction) + samples[right] * fraction)
        output.append(max(-32_768, min(32_767, value)))
    return struct.pack(f"<{len(output)}h", *output)


async def purge_audio_assets() -> None:
    """Remove prior voices/clips before a fully validated regeneration."""
    async with SessionLocal() as db:
        await db.execute(delete(MediaAsset))
        await db.commit()
    if AUDIO_DIR.exists():
        for wav_path in AUDIO_DIR.glob("*.wav"):
            wav_path.unlink()
    MANIFEST_PATH.unlink(missing_ok=True)


def write_manifest(entries: dict, failed: list[str], voice: str, model: str) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "voice": voice,
                "model": model,
                "generated_at": datetime.now(UTC).isoformat(),
                "assets": entries,
                "failed": failed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


async def generate(
    voice: str = "Kiki",
    retry_failed: bool = False,
    *,
    tts_model: str = "qwen3-tts-flash-realtime",
    replace_all: bool = False,
    validate_stt: bool = True,
    max_attempts: int = 3,
) -> None:
    gateway = QwenRealtimeGateway()
    gateway.voice = voice
    gateway.model = tts_model
    texts = await collect_texts()
    if not texts:
        print("No texts found — run import_seed first")
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if replace_all:
        await purge_audio_assets()

    prior_failed: set[str] | None = None
    entries: dict[str, dict] = {}
    if retry_failed and MANIFEST_PATH.exists():
        prior_manifest = json.loads(MANIFEST_PATH.read_text())
        prior_failed = set(prior_manifest.get("failed", []))
        entries.update(prior_manifest.get("assets", {}))
        texts = [text for text in texts if text in prior_failed]

    failed: list[str] = []
    async with SessionLocal() as db:
        for text in texts:
            content_hash = audio_content_hash(text, voice, gateway.model)
            existing = await db.execute(
                select(MediaAsset).where(MediaAsset.content_hash == content_hash)
            )
            cached = existing.scalar_one_or_none()
            if cached:
                cached_duration = (cached.duration_ms or 0) / 1000
                cached_file = (
                    Path(get_settings().local_audio_dir) / cached.storage_path
                )
                if cached_file.exists() and not cached_duration:
                    valid, cached_duration = inspect_wav(cached_file.read_bytes())
                    if valid:
                        cached.duration_ms = round(cached_duration * 1000)
                entries[text] = {
                    "content_hash": content_hash,
                    "path": cached.storage_path,
                    "url": cached.public_url or f"/media/{cached.storage_path}",
                    "duration_seconds": round(cached_duration, 3),
                }
                print(f"Skip cached: {text[:30]}")
                continue
            wav: bytes | None = None
            duration = 0.0
            transcript: str | None = None
            accepted_attempt = 0
            generation_voice = voice
            for attempt in range(1, max_attempts + 1):
                try:
                    pcm = await gateway.generate_hk_cantonese_bytes(
                        text,
                        voice=voice,
                        model=tts_model,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"Attempt {attempt} failed for {text[:30]} ({exc})")
                    continue
                if not pcm:
                    print(f"Attempt {attempt} returned no audio: {text[:30]}")
                    continue

                candidate_wav = pcm_to_wav(pcm)
                valid, candidate_duration = inspect_wav(candidate_wav)
                if not valid:
                    print(f"Attempt {attempt} produced invalid WAV: {text[:30]}")
                    continue

                if validate_stt:
                    try:
                        transcript = await transcribe_cantonese_asr(
                            candidate_wav,
                            expected_text=text,
                        )
                    except Exception as exc:  # noqa: BLE001
                        print(
                            f"Attempt {attempt} STT failed for {text[:30]} ({exc})"
                        )
                        continue
                    expected = normalize_cantonese_transcript(text)
                    actual = normalize_cantonese_transcript(transcript or "")
                    if actual != expected:
                        print(
                            f"Attempt {attempt} mismatch: {text!r} -> "
                            f"{transcript!r}"
                        )
                        continue

                wav = candidate_wav
                duration = candidate_duration
                accepted_attempt = attempt
                break

            if wav is None:
                fallback_text = COSYVOICE_PRONUNCIATION_TEXT.get(text, text)
                try:
                    fallback_pcm = await gateway.generate_cosyvoice_bytes(
                        fallback_text,
                        voice=COSYVOICE_FALLBACK_VOICE,
                        model=COSYVOICE_FALLBACK_MODEL,
                    )
                    fallback_wav = pcm_to_wav(fallback_pcm or b"")
                    valid, fallback_duration = inspect_wav(fallback_wav)
                    if valid:
                        transcript = await transcribe_cantonese_asr(
                            fallback_wav,
                            expected_text=text,
                        )
                        if normalize_cantonese_transcript(
                            transcript or ""
                        ) == normalize_cantonese_transcript(text):
                            wav = fallback_wav
                            duration = fallback_duration
                            generation_voice = COSYVOICE_FALLBACK_VOICE
                            accepted_attempt = max_attempts + 1
                            print(
                                "Generated and validated with Cantonese fallback: "
                                f"{text[:40]}"
                            )
                except Exception as exc:  # noqa: BLE001
                    print(f"Cantonese fallback failed for {text[:30]} ({exc})")

            if wav is None:
                print(f"Failed validation after {max_attempts} attempts: {text[:30]}")
                failed.append(text)
                write_manifest(entries, failed, voice, gateway.model)
                continue

            path = f"beginner/{content_hash}.wav"
            url = await upload_curriculum_audio(path, wav)
            asset = MediaAsset(
                content_hash=content_hash,
                text=text,
                voice=voice,
                model=gateway.model,
                storage_path=path,
                public_url=url,
                duration_ms=round(duration * 1000),
            )
            db.add(asset)
            entries[text] = {
                "content_hash": content_hash,
                "path": path,
                "url": url,
                "duration_seconds": round(duration, 3),
                "stt_transcript": transcript,
                "stt_validated": validate_stt,
                "generation_attempts": accepted_attempt,
                "generation_voice": generation_voice,
            }
            print(
                f"Generated and validated ({duration:.2f}s, "
                f"attempt {accepted_attempt}): {text[:40]}"
            )
            write_manifest(entries, failed, voice, gateway.model)
        await db.commit()
    if prior_failed:
        failed.extend(sorted(prior_failed.difference(texts)))
    write_manifest(entries, failed, voice, gateway.model)
    print(f"Audio complete: {len(entries)} ready, {len(failed)} failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", default="Kiki")
    parser.add_argument("--model", default="qwen3-tts-flash-realtime")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--replace-all", action="store_true")
    parser.add_argument("--skip-stt-validation", action="store_true")
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(
        generate(
            args.voice,
            args.retry_failed,
            tts_model=args.model,
            replace_all=args.replace_all,
            validate_stt=not args.skip_stt_validation,
            max_attempts=max(1, args.max_attempts),
        )
    )


if __name__ == "__main__":
    main()
