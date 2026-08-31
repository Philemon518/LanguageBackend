"""Curriculum loading and lesson rendering."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models.orm import (
    CurriculumVersion,
    ExerciseAttempt,
    Lesson,
    LessonProgress,
    MediaAsset,
    Unit,
)
from ..models.schemas import CurriculumManifest, LessonDocument, LessonSummary, UnitSummary
from .bootstrap import ensure_seed_applied
from .grading import lesson_is_complete
from .tts import audio_content_hash


@lru_cache
def _manifest_audio_urls() -> dict[str, str]:
    settings = get_settings()
    manifest_path = Path(settings.local_audio_dir) / "manifest.json"
    if not manifest_path.exists():
        return {}

    manifest = json.loads(manifest_path.read_text())
    urls: dict[str, str] = {}
    for text, entry in manifest.get("assets", {}).items():
        path = entry.get("path")
        if not path:
            continue
        if not (Path(settings.local_audio_dir) / path).exists():
            continue
        urls[text] = entry.get("url") or f"/media/{path}"
    return urls


def _audio_url_for_text(text: str, asset: MediaAsset | None) -> str | None:
    if asset:
        return asset.public_url or f"/media/{asset.storage_path}"

    manifest_url = _manifest_audio_urls().get(text)
    if manifest_url:
        return manifest_url

    settings = get_settings()
    content_hash = audio_content_hash(
        text, settings.cantonese_ai_voice_id, settings.cantonese_ai_tts_model
    )
    path = f"beginner/{content_hash}.wav"
    if (Path(settings.local_audio_dir) / path).exists():
        return f"/media/{path}"
    return None


def _cantonese_lesson_title(content: dict, stored_title: str) -> str:
    allowed_punctuation = {" ", "·", "、", "，", "：", "！", "？"}
    if stored_title and all(
        "\u3400" <= character <= "\u9fff" or character in allowed_punctuation
        for character in stored_title
    ):
        return stored_title

    target = content.get("target") or {}
    words = target.get("words") or []
    if words:
        return " · ".join(word["traditional"] for word in words)
    traditional = target.get("traditional")
    if traditional:
        return traditional
    return stored_title


async def get_latest_curriculum_version(
    db: AsyncSession, level: str = "beginner"
) -> CurriculumVersion | None:
    """Return the newest curriculum for a level with deterministic tie-breaking."""
    result = await db.execute(
        select(CurriculumVersion)
        .where(CurriculumVersion.level == level)
        .order_by(CurriculumVersion.created_at.desc(), CurriculumVersion.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _iter_audio_refs(value: Any):
    """Yield audio reference mappings at any depth in curriculum content."""
    if isinstance(value, dict):
        if value.get("text"):
            yield value
        for child in value.values():
            yield from _iter_audio_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_audio_refs(child)


def _lesson_summary_fields(content: dict, lesson, unit_phase: str) -> dict:
    target = content.get("target") or {}
    words = target.get("words") or []
    return {
        "target_traditional": target.get("traditional"),
        "target_english": target.get("english"),
        "theme": target.get("theme"),
        "word_count": len(words) if words else 1,
        "question_count": len(content.get("steps", [])),
        "phase": unit_phase,
    }


async def get_manifest(db: AsyncSession, level: str = "beginner") -> CurriculumManifest:
    await ensure_seed_applied(db)
    version = await get_latest_curriculum_version(db, level)
    if version is None:
        return CurriculumManifest(version="0.0.0", level=level, units=[])
    units_result = await db.execute(
        select(Unit).where(Unit.curriculum_version_id == version.id).order_by(Unit.sort_order)
    )
    units = units_result.scalars().all()
    summaries: list[UnitSummary] = []
    for unit in units:
        count_result = await db.execute(
            select(func.count()).select_from(Lesson).where(Lesson.unit_id == unit.id)
        )
        summaries.append(
            UnitSummary(
                id=unit.id,
                title=unit.title,
                phase=unit.phase,
                sort_order=unit.sort_order,
                lesson_count=count_result.scalar_one(),
                prerequisites=unit.prerequisites or [],
            )
        )
    return CurriculumManifest(version=version.version, level=level, units=summaries)


async def list_lessons(db: AsyncSession, unit_id: str, user_id=None) -> list[LessonSummary]:
    version = await get_latest_curriculum_version(db)
    if version is None:
        return []
    unit_result = await db.execute(
        select(Unit).where(
            Unit.id == unit_id,
            Unit.curriculum_version_id == version.id,
        )
    )
    unit = unit_result.scalar_one_or_none()
    if unit is None:
        return []
    result = await db.execute(
        select(Lesson).where(Lesson.unit_id == unit_id).order_by(Lesson.sort_order)
    )
    lessons = result.scalars().all()
    progress_map: dict[str, LessonProgress] = {}
    if user_id:
        prog = await db.execute(
            select(LessonProgress).where(
                LessonProgress.user_id == user_id,
                LessonProgress.lesson_id.in_([l.id for l in lessons]),
            )
        )
        progress_map = {p.lesson_id: p for p in prog.scalars().all()}

    return [
        LessonSummary(
            id=l.id,
            unit_id=l.unit_id,
            title=_cantonese_lesson_title(l.content_json or {}, l.title),
            lesson_type=l.lesson_type,
            sort_order=l.sort_order,
            completed=progress_map[l.id].completed if l.id in progress_map else False,
            current_step=progress_map[l.id].current_step if l.id in progress_map else 0,
            locked=False,
            **_lesson_summary_fields(l.content_json or {}, l, unit.phase if unit else "sound"),
        )
        for l in lessons
    ]


async def list_road(db: AsyncSession, user_id=None) -> list[LessonSummary]:
    await ensure_seed_applied(db)
    version = await get_latest_curriculum_version(db)
    if version is None:
        return []
    units_result = await db.execute(
        select(Unit).where(Unit.curriculum_version_id == version.id).order_by(Unit.sort_order)
    )
    units = units_result.scalars().all()
    road: list[LessonSummary] = []
    global_order = 0
    previous_completed = True
    healed = False
    all_lessons: list[Lesson] = []
    unit_lessons: list[tuple[Unit, list[Lesson]]] = []
    for unit in units:
        result = await db.execute(
            select(Lesson).where(Lesson.unit_id == unit.id).order_by(Lesson.sort_order)
        )
        lessons = result.scalars().all()
        unit_lessons.append((unit, lessons))
        all_lessons.extend(lessons)

    progress_map: dict[str, LessonProgress] = {}
    correct_by_lesson: dict[str, set[str]] = {lesson.id: set() for lesson in all_lessons}
    if user_id and all_lessons:
        prog = await db.execute(
            select(LessonProgress).where(
                LessonProgress.user_id == user_id,
                LessonProgress.lesson_id.in_([lesson.id for lesson in all_lessons]),
            )
        )
        progress_map = {row.lesson_id: row for row in prog.scalars().all()}
        attempts = await db.execute(
            select(ExerciseAttempt.lesson_id, ExerciseAttempt.exercise_id).where(
                ExerciseAttempt.user_id == user_id,
                ExerciseAttempt.lesson_id.in_([lesson.id for lesson in all_lessons]),
                ExerciseAttempt.correct.is_(True),
            )
        )
        for lesson_id, exercise_id in attempts.all():
            correct_by_lesson.setdefault(lesson_id, set()).add(exercise_id)

    for unit, lessons in unit_lessons:
        for lesson in lessons:
            content = lesson.content_json or {}
            progress = progress_map.get(lesson.id)
            completed = lesson_is_complete(
                content.get("steps", []),
                correct_by_lesson.get(lesson.id, set()),
            ) or bool(progress and progress.completed)
            if completed and progress is not None and not progress.completed:
                progress.completed = True
                progress.current_step = len(content.get("steps", []))
                healed = True
            road.append(
                LessonSummary(
                    id=lesson.id,
                    unit_id=lesson.unit_id,
                    title=_cantonese_lesson_title(content, lesson.title),
                    lesson_type=lesson.lesson_type,
                    sort_order=lesson.sort_order,
                    global_order=global_order,
                    completed=completed,
                    current_step=progress.current_step if progress else 0,
                    locked=not previous_completed,
                    **_lesson_summary_fields(content, lesson, unit.phase),
                )
            )
            global_order += 1
            previous_completed = completed

    if healed:
        await db.commit()
    return road


async def get_lesson(db: AsyncSession, lesson_id: str) -> LessonDocument | None:
    await ensure_seed_applied(db)
    version = await get_latest_curriculum_version(db)
    if version is None:
        return None
    result = await db.execute(
        select(Lesson)
        .join(Unit, Lesson.unit_id == Unit.id)
        .where(
            Lesson.id == lesson_id,
            Unit.curriculum_version_id == version.id,
        )
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        return None
    content = lesson.content_json or {}
    steps = deepcopy(content.get("steps", []))
    audio_refs = list(_iter_audio_refs(steps))
    audio_texts = {audio["text"] for audio in audio_refs}
    media_by_text: dict[str, MediaAsset] = {}
    if audio_texts:
        settings = get_settings()
        media_result = await db.execute(
            select(MediaAsset).where(
                MediaAsset.text.in_(audio_texts),
                MediaAsset.voice == settings.cantonese_ai_voice_id,
                MediaAsset.model == settings.cantonese_ai_tts_model,
            )
        )
        for asset in media_result.scalars().all():
            media_by_text.setdefault(asset.text, asset)
    for audio in audio_refs:
        asset = media_by_text.get(audio["text"])
        url = _audio_url_for_text(audio["text"], asset)
        if url:
            audio.update(
                asset_id=str(asset.id) if asset else None,
                url=url,
            )
    return LessonDocument(
        id=lesson.id,
        unit_id=lesson.unit_id,
        title=_cantonese_lesson_title(content, lesson.title),
        lesson_type=lesson.lesson_type,
        objectives=lesson.objectives or [],
        steps=steps,
        vocabulary=content.get("vocabulary", []),
        grammar_points=content.get("grammar_points", []),
        lesson_intro=content.get("lesson_intro"),
    )
