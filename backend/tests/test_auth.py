"""Authentication and account lifecycle tests."""

from collections.abc import AsyncGenerator
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.auth import router as auth_router
from app.api.learning import router as learning_router
from app.core import auth
from app.core.config import Settings
from app.core.database import Base, get_db
from app.core.migrations import migrate_user_credentials
from app.models.orm import (
    ExerciseAttempt,
    LessonProgress,
    ObjectiveMastery,
    SpeakingSession,
    UserProfile,
)


@pytest_asyncio.fixture
async def auth_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(learning_router)

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    original_secret = auth.settings.jwt_secret
    auth.settings.jwt_secret = "test-only-secret-that-is-long-enough"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, sessions
    auth.settings.jwt_secret = original_secret
    await engine.dispose()


@pytest.mark.asyncio
async def test_register_login_hash_and_wrong_password(auth_client):
    client, sessions = auth_client
    response = await client.post(
        "/auth/register",
        json={"username": "  Alice  ", "password": "correct horse battery staple"},
    )
    assert response.status_code == 201
    assert response.json()["user"]["username"] == "alice"
    assert response.json()["access_token"]

    async with sessions() as db:
        profile = (
            await db.execute(select(UserProfile).where(UserProfile.username == "alice"))
        ).scalar_one()
        assert profile.password_hash != "correct horse battery staple"
        assert auth.verify_password(
            "correct horse battery staple", profile.password_hash or ""
        )

    duplicate = await client.post(
        "/auth/register",
        json={"username": "ALICE", "password": "another secure password"},
    )
    assert duplicate.status_code == 409

    wrong = await client.post(
        "/auth/login",
        json={"username": "alice", "password": "wrong password"},
    )
    assert wrong.status_code == 401

    login = await client.post(
        "/auth/login",
        json={"username": "ALICE", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


@pytest.mark.asyncio
async def test_protected_learning_endpoint_requires_bearer(auth_client):
    client, _ = auth_client
    response = await client.get("/progress")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_delete_account_removes_owned_learning_data(auth_client):
    client, sessions = auth_client
    registered = await client.post(
        "/auth/register",
        json={"username": "learner", "password": "a secure test password"},
    )
    token = registered.json()["access_token"]
    user_id = UUID(registered.json()["user"]["id"])

    async with sessions() as db:
        db.add_all(
            [
                ExerciseAttempt(
                    user_id=user_id,
                    lesson_id="lesson",
                    exercise_id="exercise",
                    skill="reading",
                    response_json={},
                ),
                ObjectiveMastery(
                    user_id=user_id,
                    objective_id="objective",
                    skill="reading",
                ),
                LessonProgress(user_id=user_id, lesson_id="lesson"),
                SpeakingSession(user_id=user_id, session_type="drill"),
            ]
        )
        await db.commit()

    response = await client.delete(
        "/auth/account", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 204

    async with sessions() as db:
        for model in (
            ExerciseAttempt,
            ObjectiveMastery,
            LessonProgress,
            SpeakingSession,
            UserProfile,
        ):
            count = await db.scalar(select(func.count()).select_from(model))
            assert count == 0

    assert (
        await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 401


@pytest.mark.asyncio
async def test_startup_migration_adds_credentials_to_existing_sqlite_database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.exec_driver_sql(
            "CREATE TABLE user_profiles (id CHAR(32) PRIMARY KEY)"
        )
        await migrate_user_credentials(connection)

        columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]
                for column in inspect(sync_connection).get_columns("user_profiles")
            }
        )
    assert {"username", "password_hash"} <= columns
    await engine.dispose()


def test_railway_postgres_url_uses_asyncpg_driver():
    settings = Settings(
        _env_file=None,
        database_url="postgres://user:password@host:5432/canto",
    )
    assert settings.database_url == (
        "postgresql+asyncpg://user:password@host:5432/canto"
    )
