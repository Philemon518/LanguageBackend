"""Library vocabulary bank tests."""

import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import app.core.database as database_module
from app.api.auth import router as auth_router
from app.api.library import router as library_router
from app.core.database import Base, get_db
from app.models.orm import ExerciseAttempt, LessonProgress
from content.scripts.import_seed import import_seed

ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "content" / "seeds" / "beginner_v2.json"


@pytest_asyncio.fixture
async def library_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    database_module.engine = engine
    database_module.SessionLocal = sessions
    await import_seed(SEED_PATH)

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(library_router)

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, sessions


@pytest.mark.asyncio
async def test_library_empty_for_new_user(library_client):
    client, _sessions = library_client
    register = await client.post(
        "/auth/register",
        json={"username": "library_user", "password": "secret1234"},
    )
    token = register.json()["access_token"]
    response = await client.get(
        "/library",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_library_returns_encountered_words(library_client):
    client, sessions = library_client
    register = await client.post(
        "/auth/register",
        json={"username": "learner_lib", "password": "secret1234"},
    )
    body = register.json()
    token = body["access_token"]
    user_id = UUID(body["user"]["id"])

    async with sessions() as db:
        db.add(
            ExerciseAttempt(
                user_id=user_id,
                lesson_id="v2-sound-01",
                exercise_id="v2-sound-01-ex-01",
                skill="reading",
                response_json={"selected_option_id": "intro-ready"},
                correct=True,
                score=1.0,
            )
        )
        db.add(
            LessonProgress(
                user_id=user_id,
                lesson_id="v2-sound-01",
                completed=False,
                current_step=1,
            )
        )
        await db.commit()

    response = await client.get(
        "/library",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 4
    word = next(item for item in payload["words"] if item["traditional"] == "水")
    assert word["traditional"] == "水"
    assert word["english"] == "water"
    assert word["lesson_id"] == "v2-sound-01"
    assert word["word_type"] == "word"
