"""Register bundled curriculum audio files as media assets."""

import json
import logging
from pathlib import Path

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError

from ..core.config import get_settings
from ..core.database import SessionLocal, engine
from ..models.orm import MediaAsset

logger = logging.getLogger("canto.media_bootstrap")
settings = get_settings()
MEDIA_LOCK_ID = 8_192_002


async def _media_assets_ready(session) -> bool:
    count = await session.scalar(select(func.count()).select_from(MediaAsset))
    return bool(count and count > 0)


async def _sync_media_assets(session) -> tuple[int, int]:
    manifest_path = Path(settings.local_audio_dir) / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    voice = manifest.get("voice", settings.cantonese_ai_voice_id)
    model = manifest.get("model", settings.cantonese_ai_tts_model)
    assets = manifest.get("assets", {})
    if not assets:
        logger.warning("Audio manifest contains no assets")
        return 0, 0

    inserted = 0
    stale = await session.execute(
        delete(MediaAsset).where((MediaAsset.voice != voice) | (MediaAsset.model != model))
    )
    removed = stale.rowcount or 0

    with session.no_autoflush:
        for asset_text, entry in assets.items():
            content_hash = entry.get("content_hash")
            path = entry.get("path")
            if not content_hash or not path:
                continue

            existing_asset = await session.scalar(
                select(MediaAsset).where(MediaAsset.content_hash == content_hash)
            )
            public_url = entry.get("url") or f"/media/{path}"
            duration_ms = round(float(entry.get("duration_seconds", 0)) * 1000)
            if existing_asset is not None:
                existing_asset.text = asset_text
                existing_asset.voice = voice
                existing_asset.model = model
                existing_asset.storage_path = path
                existing_asset.public_url = public_url
                existing_asset.duration_ms = duration_ms
                continue

            file_path = Path(settings.local_audio_dir) / path
            if not file_path.exists():
                logger.warning("Missing audio file for %r at %s", asset_text, file_path)
                continue

            session.add(
                MediaAsset(
                    content_hash=content_hash,
                    text=asset_text,
                    voice=voice,
                    model=model,
                    storage_path=path,
                    public_url=public_url,
                    duration_ms=duration_ms,
                )
            )
            inserted += 1

    return inserted, removed


async def bootstrap_media_assets() -> None:
    manifest_path = Path(settings.local_audio_dir) / "manifest.json"
    if not manifest_path.exists():
        logger.warning("Audio manifest not found at %s", manifest_path)
        return

    async with SessionLocal() as session:
        if engine.dialect.name == "postgresql":
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": MEDIA_LOCK_ID},
            )

        try:
            inserted, removed = await _sync_media_assets(session)
            await session.flush()
            await session.commit()
            logger.info(
                "Synchronized bundled audio assets: %s inserted, %s stale removed",
                inserted,
                removed,
            )
        except IntegrityError:
            await session.rollback()
            if await _media_assets_ready(session):
                logger.info("Bundled audio already present after duplicate-key conflict")
                return

            if engine.dialect.name == "postgresql":
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_id)"),
                    {"lock_id": MEDIA_LOCK_ID},
                )
            inserted, removed = await _sync_media_assets(session)
            await session.flush()
            await session.commit()
            logger.info(
                "Synchronized bundled audio assets after retry: %s inserted, %s stale removed",
                inserted,
                removed,
            )
