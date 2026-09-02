from typing import Literal

from pydantic import BaseModel, Field


class OperationsSummary(BaseModel):
    status: Literal["ok", "attention"]
    queued_jobs: int = Field(ge=0)
    running_jobs: int = Field(ge=0)
    failed_jobs_24h: int = Field(ge=0)
    succeeded_jobs_24h: int = Field(ge=0)
    oldest_queued_seconds: int | None = Field(default=None, ge=0)
    redis_queue_depth: int | None = Field(default=None, ge=0)
    provider_invocations_24h: int = Field(ge=0)
    provider_failures_24h: int = Field(ge=0)
    estimated_provider_cost_microusd_24h: int = Field(ge=0)
    alert_codes: list[str] = Field(default_factory=list)
