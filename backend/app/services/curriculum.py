"""Curriculum loading and lesson rendering."""

import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models.orm import CurriculumVersion, Lesson, LessonProgress, MediaAsset, Unit
from ..models.schemas import CurriculumManifest, LessonDocument, LessonSummary, UnitSummary
from .qwen import audio_content_hash


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
    manifest_url = _manifest_audio_urls().get(text)
    if manifest_url:
        return manifest_url

    if asset:
        return asset.public_url or f"/media/{asset.storage_path}"

    settings = get_settings()
    content_hash = audio_content_hash(
        text, settings.qwen_tts_voice, settings.qwen_tts_model
    )
    path = f"beginner/{content_hash}.wav"
    if (Path(settings.local_audio_dir) / path).exists():
        return f"/media/{path}"
    return None


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
    version_result = await db.execute(
        select(CurriculumVersion)
        .where(CurriculumVersion.level == level)
        .order_by(CurriculumVersion.created_at.desc())
        .limit(1)
    )
    version = version_result.scalar_one_or_none()
    if version is None:
        return CurriculumManifest(version="0.0.0", level=level, units=[])
    units_result = await db.execute(
        select(Unit)
        .where(Unit.curriculum_version_id == version.id)
        .order_by(Unit.sort_order)
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


async def list_lessons(
    db: AsyncSession, unit_id: str, user_id=None
) -> list[LessonSummary]:
    unit_result = await db.execute(select(Unit).where(Unit.id == unit_id))
    unit = unit_result.scalar_one_or_none()
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
            title=l.title,
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
    version_result = await db.execute(
        select(CurriculumVersion)
        .where(CurriculumVersion.level == "beginner")
        .order_by(CurriculumVersion.created_at.desc())
        .limit(1)
    )
    version = version_result.scalar_one_or_none()
    if version is None:
        return []
    units_result = await db.execute(
        select(Unit)
        .where(Unit.curriculum_version_id == version.id)
        .order_by(Unit.sort_order)
    )
    units = units_result.scalars().all()
    road: list[LessonSummary] = []
    global_order = 0
    previous_completed = True

    for unit in units:
        result = await db.execute(
            select(Lesson).where(Lesson.unit_id == unit.id).order_by(Lesson.sort_order)
        )
        lessons = result.scalars().all()
        progress_map: dict[str, LessonProgress] = {}
        if user_id and lessons:
            prog = await db.execute(
                select(LessonProgress).where(
                    LessonProgress.user_id == user_id,
                    LessonProgress.lesson_id.in_([lesson.id for lesson in lessons]),
                )
            )
            progress_map = {p.lesson_id: p for p in prog.scalars().all()}

        for lesson in lessons:
            progress = progress_map.get(lesson.id)
            completed = bool(progress and progress.completed)
            content = lesson.content_json or {}
            road.append(
                LessonSummary(
                    id=lesson.id,
                    unit_id=lesson.unit_id,
                    title=lesson.title,
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

    return road


async def get_lesson(db: AsyncSession, lesson_id: str) -> LessonDocument | None:
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        return None
    content = lesson.content_json or {}
    steps = [dict(step) for step in content.get("steps", [])]
    audio_texts = {
        (step.get("audio") or {}).get("text")
        for step in steps
        if (step.get("audio") or {}).get("text")
    }
    audio_texts.update(
        audio.get("text")
        for step in steps
        for option in step.get("options", [])
        if (audio := option.get("audio")) and audio.get("text")
    )
    media_by_text: dict[str, MediaAsset] = {}
    if audio_texts:
        settings = get_settings()
        media_result = await db.execute(
            select(MediaAsset).where(
                MediaAsset.text.in_(audio_texts),
                MediaAsset.voice == settings.qwen_tts_voice,
                MediaAsset.model == settings.qwen_tts_model,
            )
        )
        for asset in media_result.scalars().all():
            media_by_text.setdefault(asset.text, asset)
    for step in steps:
        audio = step.get("audio")
        if audio and audio.get("text"):
            asset = media_by_text.get(audio["text"])
            url = _audio_url_for_text(audio["text"], asset)
            if url:
                step["audio"] = {
                    **audio,
                    "asset_id": str(asset.id) if asset else None,
                    "url": url,
                }
        for option in step.get("options", []):
            option_audio = option.get("audio")
            if not option_audio or not option_audio.get("text"):
                continue
            option_asset = media_by_text.get(option_audio["text"])
            option_url = _audio_url_for_text(option_audio["text"], option_asset)
            if option_url:
                option["audio"] = {
                    **option_audio,
                    "asset_id": str(option_asset.id) if option_asset else None,
                    "url": option_url,
                }
    return LessonDocument(
        id=lesson.id,
        unit_id=lesson.unit_id,
        title=lesson.title,
        lesson_type=lesson.lesson_type,
        objectives=lesson.objectives or [],
        steps=steps,
        vocabulary=content.get("vocabulary", []),
        grammar_points=content.get("grammar_points", []),
    )
