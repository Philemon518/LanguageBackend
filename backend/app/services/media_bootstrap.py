"""Register bundled curriculum audio files as media assets."""

import json
import logging
from pathlib import Path

from sqlalchemy import delete, select

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
    voice = manifest.get("voice", settings.cantonese_ai_voice_id)
    model = manifest.get("model", settings.cantonese_ai_tts_model)
    assets = manifest.get("assets", {})
    if not assets:
        logger.warning("Audio manifest contains no assets")
        return

    inserted = 0
    async with SessionLocal() as session:
        stale = await session.execute(
            delete(MediaAsset).where((MediaAsset.voice != voice) | (MediaAsset.model != model))
        )
        removed = stale.rowcount or 0
        for text, entry in assets.items():
            content_hash = entry.get("content_hash")
            path = entry.get("path")
            if not content_hash or not path:
                continue

            existing = await session.execute(
                select(MediaAsset).where(MediaAsset.content_hash == content_hash)
            )
            existing_asset = existing.scalar_one_or_none()
            if existing_asset is not None:
                existing_asset.text = text
                existing_asset.voice = voice
                existing_asset.model = model
                existing_asset.storage_path = path
                existing_asset.public_url = entry.get("url") or f"/media/{path}"
                existing_asset.duration_ms = round(float(entry.get("duration_seconds", 0)) * 1000)
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

        await session.commit()
        logger.info(
            "Synchronized bundled audio assets: %s inserted, %s stale removed",
            inserted,
            removed,
        )
