"""Register bundled curriculum audio files as media assets."""

import json
import logging
from pathlib import Path

from sqlalchemy import select

from ..core.config import get_settings
from ..core.database import SessionLocal
from ..models.orm import MediaAsset

logger = logging.getLogger("canto.media_bootstrap")
settings = get_settings()


async def bootstrap_media_assets() -> None:
    manifest_path = Path(settings.local_audio_dir) / "manifest.json"
    if not manifest_path.exists():
        logger.warning("Audio manifest not found at %s", manifest_path)
        return

    manifest = json.loads(manifest_path.read_text())
    voice = manifest.get("voice", settings.qwen_tts_voice)
    model = manifest.get("model", settings.qwen_realtime_model)
    assets = manifest.get("assets", {})
    if not assets:
        logger.warning("Audio manifest contains no assets")
        return

    inserted = 0
    async with SessionLocal() as session:
        for text, entry in assets.items():
            content_hash = entry.get("content_hash")
            path = entry.get("path")
            if not content_hash or not path:
                continue

            existing = await session.execute(
                select(MediaAsset.id).where(MediaAsset.content_hash == content_hash)
            )
            if existing.scalar_one_or_none() is not None:
                continue

            file_path = Path(settings.local_audio_dir) / path
            if not file_path.exists():
                logger.warning("Missing audio file for %r at %s", text, file_path)
                continue

            session.add(
                MediaAsset(
                    content_hash=content_hash,
                    text=text,
                    voice=voice,
                    model=model,
                    storage_path=path,
                    public_url=entry.get("url") or f"/media/{path}",
                    duration_ms=round(float(entry.get("duration_seconds", 0)) * 1000),
                )
            )
            inserted += 1

        if inserted:
            await session.commit()
            logger.info("Registered %s bundled audio assets", inserted)
        else:
            logger.info("Bundled audio assets already registered")
