from functools import lru_cache
from typing import Literal

from pydantic import EmailStr, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")

    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_log_level: str = "INFO"
    app_secret_key: str = Field(min_length=32)
    app_bootstrap_email: EmailStr | None = None
    app_bootstrap_password: str | None = Field(default=None, min_length=12)
    database_url: str
    redis_url: str
    web_origin: str = "http://localhost:3000"

    access_token_ttl_minutes: int = 60 * 12
    auth_cookie_name: str = "dd21_session"
    redis_job_queue: str = "dd21:jobs"

    media_storage_backend: Literal["filesystem", "railway_s3"] = "filesystem"
    media_root: str = "/data/media"
    media_max_audio_bytes: int = 25_000_000
    bucket: str | None = None
    access_key_id: str | None = None
    secret_access_key: SecretStr | None = None
    region: str | None = None
    endpoint: str | None = None

    speech_consent_version: str = "2026-09-02-v1"
    speech_transcription_provider: Literal["mock", "openai"] = "mock"
    speech_provider_timeout_seconds: float = 90.0
    openai_api_key: SecretStr | None = None
    openai_transcription_model: str = "gpt-4o-transcribe"

    @property
    def web_origins(self) -> list[str]:
        return [origin.strip() for origin in self.web_origin.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env in {"staging", "production"}:
            if not self.app_bootstrap_email or not self.app_bootstrap_password:
                raise ValueError("bootstrap credentials are required outside development/test")
            if "dev-only" in self.app_bootstrap_password.lower():
                raise ValueError(
                    "development bootstrap password cannot be used outside development/test"
                )
            if self.media_storage_backend != "railway_s3":
                raise ValueError(
                    "staging/production speech media must use Railway S3-compatible bucket storage"
                )
            if not all(
                [
                    self.bucket,
                    self.access_key_id,
                    self.secret_access_key,
                    self.region,
                    self.endpoint,
                ]
            ):
                raise ValueError("Railway Bucket credentials are required outside development/test")
            if self.speech_transcription_provider != "openai":
                raise ValueError(
                    "staging/production must use a real speech transcription provider"
                )
        if self.speech_transcription_provider == "openai" and self.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is required when speech provider is openai")
        return self

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url.startswith("postgresql+psycopg://"):
            return self.database_url
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
