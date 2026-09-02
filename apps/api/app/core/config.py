from functools import lru_cache
from typing import Literal

from pydantic import EmailStr, Field, model_validator
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

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env in {"staging", "production"}:
            if not self.app_bootstrap_email or not self.app_bootstrap_password:
                raise ValueError("bootstrap credentials are required outside development/test")
            if "dev-only" in self.app_bootstrap_password.lower():
                raise ValueError(
                    "development bootstrap password cannot be used outside development/test"
                )
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
