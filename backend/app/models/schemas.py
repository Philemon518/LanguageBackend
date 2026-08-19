"""Pydantic API schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


class AuthCredentials(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: UUID
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CurriculumManifest(BaseModel):
    version: str
    level: str
    units: list["UnitSummary"]


class UnitSummary(BaseModel):
    id: str
    title: str
    phase: str
    sort_order: int
    lesson_count: int
    prerequisites: list[str] = Field(default_factory=list)


class LessonSummary(BaseModel):
    id: str
    unit_id: str
    title: str
    lesson_type: str
    sort_order: int
    global_order: int = 0
    question_count: int = 0
    phase: str = "sound"
    completed: bool = False
    current_step: int = 0
    locked: bool = True


class AudioRef(BaseModel):
    asset_id: str | None = None
    url: str | None = None
    text: str | None = None


class ExerciseOption(BaseModel):
    id: str
    label: str
    jyutping: str | None = None
    audio: AudioRef | None = None


class ExerciseStep(BaseModel):
    id: str
    type: str
    skill: str
    prompt: str
    audio: AudioRef | None = None
    options: list[ExerciseOption] = Field(default_factory=list)
    correct_option_id: str | None = None
    reveal_jyutping: str | None = None
    reveal_character: str | None = None
    reveal_english: str | None = None
    hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LessonDocument(BaseModel):
    id: str
    unit_id: str
    title: str
    lesson_type: str
    objectives: list[str]
    steps: list[ExerciseStep]
    vocabulary: list[dict[str, Any]] = Field(default_factory=list)
    grammar_points: list[dict[str, Any]] = Field(default_factory=list)


class AttemptRequest(BaseModel):
    lesson_id: str
    exercise_id: str
    skill: str
    response: dict[str, Any]
    idempotency_key: str | None = None


class AttemptResponse(BaseModel):
    id: UUID
    correct: bool
    score: float
    feedback: str | None
    mastery_delta: dict[str, float] = Field(default_factory=dict)
    skill_point_awarded: bool = False


class ProgressResponse(BaseModel):
    level: str
    streak_days: int
    total_xp: int
    lessons_completed: int
    mastery: list[dict[str, Any]]
    review_queue: list[str] = Field(default_factory=list)


class SkillProgress(BaseModel):
    skill: str
    completed: int
    total: int
    percentage: float


class SkillSummaryResponse(BaseModel):
    skills: list[SkillProgress]


class PracticeNextResponse(BaseModel):
    lesson_id: str
    exercise_id: str
    reason: str


class ConversationCreate(BaseModel):
    scenario_id: str
    target_vocab: list[str] = Field(default_factory=list)
    grammar_limits: list[str] = Field(default_factory=list)


class ConversationSession(BaseModel):
    id: UUID
    scenario_id: str
    target_vocab: list[str]
    ws_url: str
    instructions: str


class SpeechDrillCreate(BaseModel):
    lesson_id: str
    exercise_id: str
    expected_text: str
    expected_jyutping: str | None = None


class SpeechDrillSession(BaseModel):
    id: UUID
    ws_url: str


class StoryDocument(BaseModel):
    id: str
    title: str
    level: str
    audio: AudioRef
    sentences: list[dict[str, Any]]
    comprehension_questions: list[ExerciseStep]


class WritingPrompt(BaseModel):
    id: str
    prompt: str
    expected_patterns: list[str]
    target_vocab: list[str]
    min_length: int = 1


class WritingFeedback(BaseModel):
    acceptable: bool
    feedback: str
    matched_vocab: list[str]
    matched_patterns: list[str]
