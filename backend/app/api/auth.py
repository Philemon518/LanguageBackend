"""Username/password account endpoints."""

import unicodedata
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import (
    AuthUser,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..core.config import get_settings
from ..core.database import get_db
from ..models.orm import (
    ExerciseAttempt,
    LessonProgress,
    ObjectiveMastery,
    SpeakingSession,
    UserProfile,
)
from ..models.schemas import AuthCredentials, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def normalize_username(username: str) -> str:
    normalized = unicodedata.normalize("NFKC", username).strip().casefold()
    if not 3 <= len(normalized) <= 64:
        raise HTTPException(422, "Username must be 3 to 64 characters after normalization")
    return normalized


def token_response(profile: UserProfile) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(profile.id),
        user=UserResponse(id=profile.id, username=profile.username or ""),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: AuthCredentials,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    username = normalize_username(body.username)
    existing = await db.execute(select(UserProfile.id).where(UserProfile.username == username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username is already registered")

    profile = UserProfile(
        id=uuid.uuid4(),
        username=username,
        password_hash=hash_password(body.password),
        display_name=username,
    )
    db.add(profile)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Username is already registered"
        ) from None
    await db.refresh(profile)
    return token_response(profile)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: AuthCredentials,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    username = normalize_username(body.username)
    result = await db.execute(select(UserProfile).where(UserProfile.username == username))
    profile = result.scalar_one_or_none()
    if (
        profile is None
        or profile.password_hash is None
        or not verify_password(body.password, profile.password_hash)
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_response(profile)


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[AuthUser, Depends(get_current_user)]):
    return UserResponse(id=user.id, username=user.username)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    session_result = await db.execute(
        select(SpeakingSession.id).where(SpeakingSession.user_id == user.id)
    )
    transcript_dir = Path(settings.local_user_dir) / "transcripts"
    for session_id in session_result.scalars().all():
        (transcript_dir / f"{session_id}.json").unlink(missing_ok=True)
    for model in (ExerciseAttempt, ObjectiveMastery, LessonProgress, SpeakingSession):
        await db.execute(delete(model).where(model.user_id == user.id))
    await db.execute(delete(UserProfile).where(UserProfile.id == user.id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
