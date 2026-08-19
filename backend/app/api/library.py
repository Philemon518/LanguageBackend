"""Personal vocabulary library endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import AuthUser, get_current_user
from ..core.database import get_db
from ..models.schemas import LibraryResponse
from ..services.library import get_user_library

router = APIRouter(prefix="/library", tags=["library"])


@router.get("", response_model=LibraryResponse)
async def library_words(
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    words = await get_user_library(db, user.id)
    return LibraryResponse(words=words, total=len(words))
