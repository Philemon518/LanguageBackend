"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .api.auth import router as auth_router
from .api.curriculum import router as curriculum_router
from .api.learning import router as learning_router
from .api.library import router as library_router
from .api.speech import router as speech_router
from .core.config import get_settings
from .core.database import Base, engine, get_db
from .core.migrations import migrate_user_credentials
from .models.orm import CurriculumVersion, Lesson, Unit
from .models.schemas import HealthResponse
from .services.bootstrap import bootstrap_if_empty
from .services.media_bootstrap import bootstrap_media_assets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("canto")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.local_data_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.local_audio_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.local_user_dir).mkdir(parents=True, exist_ok=True)
    if settings.app_env != "development" and not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is required outside development")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await migrate_user_credentials(conn)
    logger.info("Database tables and credential columns ensured")

    await bootstrap_if_empty()
    logger.info("Curriculum bootstrap finished")
    try:
        await bootstrap_media_assets()
    except Exception:
        logger.exception("Media bootstrap failed; continuing with manifest fallbacks")
    else:
        logger.info("Media bootstrap finished")

    yield


app = FastAPI(title="Canto API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(curriculum_router)
app.include_router(learning_router)
app.include_router(library_router)
app.include_router(speech_router)
app.mount(
    "/media",
    StaticFiles(directory=settings.local_audio_dir, check_dir=False),
    name="media",
)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Liveness probe for Railway — must stay fast and not block on seed import."""
    return HealthResponse()


@app.get("/ready", response_model=HealthResponse)
async def ready(db: Annotated[AsyncSession, Depends(get_db)]):
    """Readiness probe — verifies database connectivity and curriculum presence."""
    await db.execute(text("SELECT 1"))
    curriculum = await db.execute(select(CurriculumVersion.id).limit(1))
    if curriculum.scalar_one_or_none() is None:
        from fastapi import HTTPException

        raise HTTPException(503, "Curriculum bootstrap still in progress")
    lesson_count = await db.scalar(select(func.count()).select_from(Lesson)) or 0
    unit_titles = list((await db.scalars(select(Unit.title).order_by(Unit.sort_order))).all())
    return HealthResponse(
        status="ready",
        units=len(unit_titles),
        lessons=lesson_count,
        unit_titles=unit_titles,
    )
