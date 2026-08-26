"""Tests for bundled audio registration and URL resolution."""

from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.models.orm import MediaAsset
from app.services.curriculum import _audio_url_for_text
from app.services.media_bootstrap import bootstrap_media_assets


@pytest.mark.asyncio
async def test_bootstrap_media_assets_registers_manifest():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await bootstrap_media_assets()
    async with SessionLocal() as session:
        result = await session.execute(
            select(MediaAsset).where(MediaAsset.text == "廣東話")
        )
        asset = result.scalar_one_or_none()
    assert asset is not None
    assert _audio_url_for_text("廣東話", asset).endswith(".wav")


@pytest.mark.asyncio
async def test_bootstrap_media_assets_is_idempotent():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await bootstrap_media_assets()
    await bootstrap_media_assets()
    async with SessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(MediaAsset))
    assert count and count > 0


@pytest.mark.asyncio
async def test_bootstrap_media_assets_tolerates_existing_rows():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await bootstrap_media_assets()
    async with SessionLocal() as session:
        before = await session.scalar(select(func.count()).select_from(MediaAsset))
    await bootstrap_media_assets()
    async with SessionLocal() as session:
        after = await session.scalar(select(func.count()).select_from(MediaAsset))
    assert before and before > 0
    assert before == after


@pytest.mark.asyncio
async def test_audio_url_falls_back_to_manifest():
    settings = get_settings()
    url = _audio_url_for_text("廣東話", None)
    assert url is not None
    path = Path(settings.local_audio_dir) / url.removeprefix("/media/")
    assert path.exists()
