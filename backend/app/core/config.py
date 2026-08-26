"""Application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "*"

    database_url: str = f"sqlite+aiosqlite:///{Path(__file__).resolve().parents[2] / 'canto.db'}"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    local_data_dir: str = "./local_data"
    local_audio_dir: str = "./local_data/audio"
    local_user_dir: str = "./local_data/user"

    dashscope_api_key: str = ""
    qwen_realtime_model: str = "qwen3.5-omni-plus-realtime"
    qwen_tts_model: str = "qwen3-tts-flash-realtime"
    qwen_tts_voice: str = "Kiki"
    qwen_realtime_url: str = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"

    cantonese_ai_api_key: str = ""
    cantonese_ai_tts_url: str = "https://cantonese.ai/api/tts"
    cantonese_ai_tts_model: str = "v6"
    cantonese_ai_voice_id: str = "50a9a698-1f99-437c-a07d-9cad435c5f8a"

    max_conversation_minutes: int = 15
    max_speech_requests_per_hour: int = 60
    rate_limit_enabled: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Convert Railway Postgres URLs to SQLAlchemy asyncpg."""
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://") and "+asyncpg" not in value:
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def signing_secret(self) -> str:
        if self.jwt_secret:
            return self.jwt_secret
        if self.app_env == "development":
            return "canto-local-development-only"
        raise RuntimeError("JWT_SECRET is required outside development")


@lru_cache
def get_settings() -> Settings:
    return Settings()
