"""Register bundled curriculum audio files as media assets."""

import json
import logging
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from ..core.config import get_settings
from ..core.database import SessionLocal, engine
from ..models.orm import MediaAsset

logger = logging.getLogger("canto.media_bootstrap")
settings = get_settings()
MEDIA_LOCK_ID = 8_192_002


async def _media_assets_ready(session, expected_count: int | None = None) -> bool:
    count = await session.scalar(select(func.count()).select_from(MediaAsset))
    if not count:
        return False
    if expected_count is not None:
        return count >= expected_count
    return True


def _load_manifest() -> tuple[str, str, dict] | None:
    manifest_path = Path(settings.local_audio_dir) / "manifest.json"
    if not manifest_path.exists():
        return None

    manifest = json.loads(manifest_path.read_text())
    voice = manifest.get("voice", settings.cantonese_ai_voice_id)
    model = manifest.get("model", settings.cantonese_ai_tts_model)
    assets = manifest.get("assets", {})
    if not assets:
        return None
    return voice, model, assets


async def _sync_media_assets(session, voice: str, model: str, assets: dict) -> tuple[int, int]:
    inserted = 0
    updated = 0
    pending_hashes: set[str] = set()

    with session.no_autoflush:
        for asset_text, entry in assets.items():
            content_hash = entry.get("content_hash")
            path = entry.get("path")
            if not content_hash or not path:
                continue
            if content_hash in pending_hashes:
                continue
            pending_hashes.add(content_hash)

            public_url = entry.get("url") or f"/media/{path}"
            duration_ms = round(float(entry.get("duration_seconds", 0)) * 1000)
            existing_asset = await session.scalar(
                select(MediaAsset).where(MediaAsset.content_hash == content_hash)
            )
            if existing_asset is not None:
                existing_asset.text = asset_text
                existing_asset.voice = voice
                existing_asset.model = model
                existing_asset.storage_path = path
                existing_asset.public_url = public_url
                existing_asset.duration_ms = duration_ms
                updated += 1
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

    return inserted, updated


async def bootstrap_media_assets() -> None:
    manifest = _load_manifest()
    if manifest is None:
        logger.warning("Audio manifest not found or empty at %s", settings.local_audio_dir)
        return

    voice, model, assets = manifest
    expected_assets = sum(
        1
        for entry in assets.values()
        if entry.get("content_hash")
        and entry.get("path")
        and (Path(settings.local_audio_dir) / entry["path"]).exists()
    )

    async with SessionLocal() as session:
        if engine.dialect.name == "postgresql":
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": MEDIA_LOCK_ID},
            )

        try:
            inserted, updated = await _sync_media_assets(session, voice, model, assets)
            await session.flush()
            await session.commit()
            logger.info(
                "Synchronized bundled audio assets: %s inserted, %s updated",
                inserted,
                updated,
            )
            return
        except IntegrityError as exc:
            await session.rollback()
            logger.warning("Media bootstrap duplicate-key conflict: %s", exc)

    async with SessionLocal() as session:
        if await _media_assets_ready(session, expected_assets):
            logger.info("Bundled audio already present after duplicate-key conflict")
            return

    logger.warning(
        "Media bootstrap incomplete; API will continue using bundled manifest fallbacks"
    )
