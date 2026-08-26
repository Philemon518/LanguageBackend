"""Tests for bundled audio registration and URL resolution."""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.orm import MediaAsset
from app.services.curriculum import _audio_url_for_text
from app.services.media_bootstrap import bootstrap_media_assets


@pytest.mark.asyncio
async def test_bootstrap_media_assets_registers_manifest():
    await bootstrap_media_assets()
    async with SessionLocal() as session:
        result = await session.execute(
            select(MediaAsset).where(MediaAsset.text == "廣東話")
        )
        asset = result.scalar_one_or_none()
    assert asset is not None
    assert _audio_url_for_text("廣東話", asset).endswith(".wav")


@pytest.mark.asyncio
async def test_audio_url_falls_back_to_manifest():
    settings = get_settings()
    url = _audio_url_for_text("廣東話", None)
    assert url is not None
    path = Path(settings.local_audio_dir) / url.removeprefix("/media/")
    assert path.exists()
