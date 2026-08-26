"""Personal vocabulary bank built from lessons the learner has touched."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models.orm import ExerciseAttempt, Lesson, LessonProgress, Lexeme, MediaAsset, Unit
from .curriculum import _audio_url_for_text, get_latest_curriculum_version


async def get_user_library(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Return lexemes from lessons the user has started or attempted."""

    attempt_rows = await db.execute(
        select(
            ExerciseAttempt.lesson_id,
            func.min(ExerciseAttempt.created_at).label("encountered_at"),
        )
        .where(ExerciseAttempt.user_id == user_id)
        .group_by(ExerciseAttempt.lesson_id)
    )
    attempt_map = {lesson_id: encountered_at for lesson_id, encountered_at in attempt_rows.all()}

    progress_rows = await db.execute(
        select(LessonProgress).where(
            LessonProgress.user_id == user_id,
            LessonProgress.current_step > 0,
        )
    )
    for progress in progress_rows.scalars().all():
        attempt_map.setdefault(progress.lesson_id, progress.updated_at)

    if not attempt_map:
        return []

    version = await get_latest_curriculum_version(db)
    if version is None:
        return []

    units_result = await db.execute(
        select(Unit).where(Unit.curriculum_version_id == version.id).order_by(Unit.sort_order)
    )
    units = units_result.scalars().all()
    unit_phase = {unit.id: unit.phase for unit in units}
    lesson_order: dict[str, int] = {}
    order = 0
    for unit in units:
        lessons_result = await db.execute(
            select(Lesson).where(Lesson.unit_id == unit.id).order_by(Lesson.sort_order)
        )
        for lesson in lessons_result.scalars().all():
            lesson_order[lesson.id] = order
            order += 1

    attempt_map = {
        lesson_id: encountered_at
        for lesson_id, encountered_at in attempt_map.items()
        if lesson_id in lesson_order
    }
    if not attempt_map:
        return []

    lessons_result = await db.execute(select(Lesson).where(Lesson.id.in_(attempt_map.keys())))
    lessons = lessons_result.scalars().all()

    lexeme_ids: set[str] = set()
    lesson_lexemes: dict[str, list[str]] = {}
    lesson_meta: dict[str, dict] = {}
    for lesson in lessons:
        content = lesson.content_json or {}
        target = content.get("target") or {}
        vocabulary = content.get("vocabulary") or []
        intro_meta_by_objective = {
            (step.get("metadata") or {}).get("objective_id"): step.get("metadata") or {}
            for step in content.get("steps", [])
            if step.get("type") == "word_intro"
        }

        lesson_lexeme_list: list[str] = []
        for vocabulary_entry in vocabulary:
            lexeme_id = vocabulary_entry.get("lexeme_id")
            if not lexeme_id:
                continue
            lexeme_ids.add(lexeme_id)
            lesson_lexeme_list.append(lexeme_id)
        if lesson_lexeme_list:
            lesson_lexemes[lesson.id] = lesson_lexeme_list

        lesson_meta[lesson.id] = {
            "lesson_title": lesson.title,
            "lesson_type": lesson.lesson_type,
            "phase": unit_phase.get(lesson.unit_id, "sound"),
            "encountered_at": attempt_map.get(lesson.id),
            "global_order": lesson_order.get(lesson.id, 0),
            "target": target,
            "intro_meta_by_objective": intro_meta_by_objective,
        }

    if not lexeme_ids:
        return []

    lexeme_rows = await db.execute(select(Lexeme).where(Lexeme.id.in_(lexeme_ids)))
    lexeme_by_id = {row.id: row for row in lexeme_rows.scalars().all()}

    audio_texts = {row.traditional for row in lexeme_by_id.values()}
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

    entries: list[dict] = []
    for lesson_id, lesson_lexeme_list in lesson_lexemes.items():
        meta = lesson_meta[lesson_id]
        target = meta["target"]
        encountered_at: datetime | None = meta["encountered_at"]
        for lexeme_id in lesson_lexeme_list:
            lexeme = lexeme_by_id.get(lexeme_id)
            if lexeme is None:
                continue
            objective_id = lexeme_id.replace("-word-", "-obj-")
            intro_meta = meta["intro_meta_by_objective"].get(objective_id, {})
            entries.append(
                {
                    "lexeme_id": lexeme.id,
                    "traditional": lexeme.traditional,
                    "jyutping": lexeme.jyutping,
                    "tone": lexeme.tone,
                    "english": lexeme.english,
                    "word_type": intro_meta.get("word_type"),
                    "components": intro_meta.get("components_label"),
                    "phase": meta["phase"],
                    "lesson_id": lesson_id,
                    "lesson_title": meta["lesson_title"],
                    "lesson_type": meta["lesson_type"],
                    "encountered_at": encountered_at.isoformat() if encountered_at else None,
                    "audio_url": _audio_url_for_text(
                        lexeme.traditional,
                        media_by_text.get(lexeme.traditional),
                    ),
                    "context_traditional": target.get("traditional"),
                    "context_jyutping": target.get("jyutping"),
                    "context_english": target.get("english"),
                    "_global_order": meta["global_order"],
                }
            )

    entries.sort(
        key=lambda item: (
            item["encountered_at"] is None,
            item["encountered_at"] or "",
            -item["_global_order"],
        ),
        reverse=True,
    )
    for entry in entries:
        entry.pop("_global_order", None)
    return entries
