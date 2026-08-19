"""Local filesystem storage helpers."""

import logging
from pathlib import Path

from ..core.config import get_settings

logger = logging.getLogger("canto.storage")
settings = get_settings()


async def upload_curriculum_audio(path: str, data: bytes, content_type: str = "audio/wav") -> str | None:
    target = Path(settings.local_audio_dir) / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    logger.info("Stored audio locally at %s", target)
    return f"/media/{path}"
