"""Curriculum endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import AuthUser, get_optional_user
from ..core.database import get_db
from ..models.schemas import CurriculumManifest, LessonDocument, LessonSummary
from ..services.curriculum import get_lesson, get_manifest, list_lessons, list_road

router = APIRouter(prefix="/curriculum", tags=["curriculum"])


@router.get("/manifest", response_model=CurriculumManifest)
async def curriculum_manifest(db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_manifest(db)


@router.get("/units/{unit_id}/lessons", response_model=list[LessonSummary])
async def unit_lessons(
    unit_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[AuthUser | None, Depends(get_optional_user)] = None,
):
    return await list_lessons(db, unit_id, user.id if user else None)


@router.get("/road", response_model=list[LessonSummary])
async def curriculum_road(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[AuthUser | None, Depends(get_optional_user)] = None,
):
    return await list_road(db, user.id if user else None)


@router.get("/lessons/{lesson_id}", response_model=LessonDocument)
async def lesson_detail(
    lesson_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    doc = await get_lesson(db, lesson_id)
    if not doc:
        raise HTTPException(404, "Lesson not found")
    return doc
