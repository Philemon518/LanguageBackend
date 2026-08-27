"""Generate Cantonese curriculum audio with Gigi and validate it with Qwen STT."""

import argparse
import asyncio
import io
import json
import struct
import sys
import time
import unicodedata
import wave
from datetime import UTC, datetime
from pathlib import Path

import httpx

from opencc import OpenCC

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.models.orm import CurriculumVersion, Lesson, MediaAsset, Unit
from app.services.qwen import transcribe_cantonese_asr
from app.services.storage import upload_curriculum_audio
from app.services.tts import CantoneseAiTTSGateway, audio_content_hash


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
# The live cantonese.ai plan currently allows 4 TTS requests per minute.
TTS_MIN_INTERVAL_SECONDS = 16.0
S2T_CONVERTER = OpenCC("s2t")


async def collect_audio_refs() -> list[dict[str, str]]:
    refs: dict[str, dict[str, str]] = {}

    def collect(value) -> None:
        if isinstance(value, dict):
            text = value.get("text")
            jyutping = value.get("jyutping")
            if text and jyutping:
                refs.setdefault(text, {"text": text, "jyutping": jyutping})
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

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
            select(Lesson)
            .join(Unit, Lesson.unit_id == Unit.id)
            .where(Unit.curriculum_version_id == version.id)
        )
        for lesson in result.scalars().all():
            collect((lesson.content_json or {}).get("steps", []))
    return list(refs.values())


def inspect_wav(data: bytes) -> tuple[bool, float]:
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            duration = wav.getnframes() / max(wav.getframerate(), 1)
            valid = wav.getnchannels() == 1 and wav.getsampwidth() == 2 and duration >= 0.08
            return valid, duration
    except (wave.Error, EOFError):
        return False, 0.0


def normalize_cantonese_transcript(text: str) -> str:
    """Normalize formatting while preserving every spoken character/particle."""
    normalized = S2T_CONVERTER.convert(unicodedata.normalize("NFKC", text).strip())
    return "".join(
        char
        for char in normalized
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def transcripts_match(expected: str, actual: str) -> bool:
    """Accept exact speech, plus ASR particles on isolated syllables."""
    expected_n = normalize_cantonese_transcript(expected)
    actual_n = normalize_cantonese_transcript(actual)
    if actual_n == expected_n:
        return bool(expected_n)
    if len(expected_n) == 1 and expected_n in actual_n:
        return True
    # Isolated 五 (ng5) is consistently heard as a nasal filler by Qwen STT.
    if expected_n == "五" and actual_n in {"嗯", "唔"}:
        return True
    return False


def resample_pcm16(pcm: bytes, source_rate: int = 24_000, target_rate: int = 16_000) -> bytes:
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


async def synthesize(
    gateway: CantoneseAiTTSGateway,
    text: str,
    jyutping: str,
    voice: str,
    model: str,
    last_request_at: list[float],
) -> bytes | None:
    elapsed = time.monotonic() - last_request_at[0]
    if last_request_at[0] and elapsed < TTS_MIN_INTERVAL_SECONDS:
        await asyncio.sleep(TTS_MIN_INTERVAL_SECONDS - elapsed)
    try:
        audio = await gateway.generate_audio(
            text,
            jyutping=jyutping,
            voice_id=voice,
            model_id=model,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code == 429:
            print(f"Rate limited on {text[:30]} — waiting 20s")
            await asyncio.sleep(20)
            audio = await gateway.generate_audio(
                text,
                jyutping=jyutping,
                voice_id=voice,
                model_id=model,
            )
        else:
            raise
    last_request_at[0] = time.monotonic()
    return audio


async def generate(
    retry_failed: bool = False,
    *,
    replace_all: bool = False,
    validate_stt: bool = True,
    max_attempts: int = 3,
) -> None:
    settings = get_settings()
    gateway = CantoneseAiTTSGateway(settings=settings)
    voice = settings.cantonese_ai_voice_id
    model = settings.cantonese_ai_tts_model
    last_request_at = [0.0]
    audio_refs = await collect_audio_refs()
    if not audio_refs:
        print("No audio references found — run import_seed first")
        return

    prior_failed: set[str] | None = None
    entries: dict[str, dict] = {}
    if retry_failed and MANIFEST_PATH.exists():
        prior_manifest = json.loads(MANIFEST_PATH.read_text())
        prior_failed = set(prior_manifest.get("failed", []))
        entries.update(prior_manifest.get("assets", {}))
        audio_refs = [audio_ref for audio_ref in audio_refs if audio_ref["text"] in prior_failed]
    elif not replace_all and MANIFEST_PATH.exists():
        prior_manifest = json.loads(MANIFEST_PATH.read_text())
        entries.update(prior_manifest.get("assets", {}))
        audio_dir = Path(settings.local_audio_dir)
        remaining = []
        for audio_ref in audio_refs:
            entry = entries.get(audio_ref["text"])
            bundled = audio_dir / entry["path"] if entry and entry.get("path") else None
            if bundled is not None and bundled.exists():
                print(f"Skip bundled: {audio_ref['text'][:30]}")
                continue
            remaining.append(audio_ref)
        audio_refs = remaining
        if not audio_refs:
            write_manifest(entries, [], voice, model)
            print(f"Audio complete: {len(entries)} ready, 0 failed")
            return

    print(f"Generating {len(audio_refs)} unique Gigi clips (throttled to 4/min)")
    preflight_ref = audio_refs[0]
    preflight_wav = None
    if not retry_failed:
        preflight_wav = await synthesize(
            gateway,
            preflight_ref["text"],
            preflight_ref["jyutping"],
            voice,
            model,
            last_request_at,
        )
        preflight_valid, _ = inspect_wav(preflight_wav or b"")
        if not preflight_valid:
            raise RuntimeError("cantonese.ai preflight returned invalid WAV audio")
        print(f"Preflight OK: {preflight_ref['text']}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if replace_all:
        await purge_audio_assets()
        entries = {}

    failed: list[str] = []
    async with SessionLocal() as db:
        for audio_ref in audio_refs:
            text = audio_ref["text"]
            jyutping = audio_ref["jyutping"]
            content_hash = audio_content_hash(text, voice, model)
            existing = await db.execute(
                select(MediaAsset).where(MediaAsset.content_hash == content_hash)
            )
            cached = existing.scalar_one_or_none()
            if cached:
                cached_duration = (cached.duration_ms or 0) / 1000
                cached_file = Path(get_settings().local_audio_dir) / cached.storage_path
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
            for attempt in range(1, max_attempts + 1):
                try:
                    if attempt == 1 and text == preflight_ref["text"] and preflight_wav:
                        candidate_wav = preflight_wav
                    else:
                        candidate_wav = await synthesize(
                            gateway,
                            text,
                            jyutping,
                            voice,
                            model,
                            last_request_at,
                        )
                except Exception as exc:  # noqa: BLE001
                    print(f"Attempt {attempt} failed for {text[:30]} ({exc})")
                    continue
                if not candidate_wav:
                    print(f"Attempt {attempt} returned no audio: {text[:30]}")
                    continue

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
                        print(f"Attempt {attempt} STT failed for {text[:30]} ({exc})")
                        continue
                    if not transcripts_match(text, transcript or ""):
                        print(f"Attempt {attempt} mismatch: {text!r} -> {transcript!r}")
                        continue

                wav = candidate_wav
                duration = candidate_duration
                accepted_attempt = attempt
                break

            if wav is None:
                print(f"Failed validation after {max_attempts} attempts: {text[:30]}")
                failed.append(text)
                write_manifest(entries, failed, voice, model)
                continue

            path = f"beginner/{content_hash}.wav"
            url = await upload_curriculum_audio(path, wav)
            asset = MediaAsset(
                content_hash=content_hash,
                text=text,
                voice=voice,
                model=model,
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
                "jyutping": jyutping,
                "generation_attempts": accepted_attempt,
                "generation_voice": "Gigi",
            }
            print(
                f"Generated and validated ({duration:.2f}s, "
                f"attempt {accepted_attempt}): {text[:40]}"
            )
            write_manifest(entries, failed, voice, model)
        await db.commit()
    if prior_failed:
        attempted_texts = {audio_ref["text"] for audio_ref in audio_refs}
        failed.extend(sorted(prior_failed.difference(attempted_texts)))
    write_manifest(entries, failed, voice, model)
    print(f"Audio complete: {len(entries)} ready, {len(failed)} failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--replace-all", action="store_true")
    parser.add_argument("--skip-stt-validation", action="store_true")
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(
        generate(
            args.retry_failed,
            replace_all=args.replace_all,
            validate_stt=not args.skip_stt_validation,
            max_attempts=max(1, args.max_attempts),
        )
    )


if __name__ == "__main__":
    main()
