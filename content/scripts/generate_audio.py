"""Generate and cache curriculum audio via Qwen TTS."""

import asyncio
import argparse
import json
import io
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal, engine, Base  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.models.orm import CurriculumVersion, Lesson, MediaAsset, Unit  # noqa: E402
from app.services.qwen import QwenRealtimeGateway, audio_content_hash  # noqa: E402
from app.services.storage import upload_curriculum_audio  # noqa: E402


def pcm_to_wav(pcm: bytes, sample_rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


MANIFEST_PATH = ROOT / "backend" / "local_data" / "audio" / "manifest.json"


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


def write_manifest(entries: dict, failed: list[str], voice: str, model: str) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "voice": voice,
                "model": model,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "assets": entries,
                "failed": failed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


async def generate(voice: str = "Kiki", retry_failed: bool = False) -> None:
    gateway = QwenRealtimeGateway()
    gateway.voice = voice
    texts = await collect_texts()
    if not texts:
        print("No texts found — run import_seed first")
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    prior_failed: set[str] | None = None
    if retry_failed and MANIFEST_PATH.exists():
        prior_failed = set(json.loads(MANIFEST_PATH.read_text()).get("failed", []))
        texts = [text for text in texts if text in prior_failed]

    entries: dict[str, dict] = {}
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
            try:
                pcm = await gateway.generate_tts_bytes(text, voice)
            except Exception as exc:
                print(f"Failed: {text[:30]} ({exc})")
                failed.append(text)
                continue
            if not pcm:
                print(f"Failed (no audio returned): {text[:30]}")
                failed.append(text)
                continue
            wav = pcm_to_wav(pcm)
            valid, duration = inspect_wav(wav)
            if not valid:
                print(f"Failed WAV validation: {text[:30]}")
                failed.append(text)
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
            }
            print(f"Generated ({duration:.2f}s): {text[:40]}")
            write_manifest(entries, failed, voice, gateway.model)
        await db.commit()
    if prior_failed:
        failed.extend(sorted(prior_failed.difference(texts)))
    write_manifest(entries, failed, voice, gateway.model)
    print(f"Audio complete: {len(entries)} ready, {len(failed)} failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", default="Kiki")
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()
    asyncio.run(generate(args.voice, args.retry_failed))


if __name__ == "__main__":
    main()
