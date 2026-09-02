from typing import Literal

import redis.asyncio as redis
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "error"] | None = None
    redis: Literal["ok", "error"] | None = None


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
async def ready(session: DbSession) -> HealthResponse:
    settings = get_settings()
    database_status: Literal["ok", "error"] = "ok"
    redis_status: Literal["ok", "error"] = "ok"

    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # readiness must aggregate dependency state
        database_status = "error"

    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.ping()
    except redis.RedisError:
        redis_status = "error"
    finally:
        await client.aclose()

    overall_status = "ok" if database_status == redis_status == "ok" else "degraded"
    return HealthResponse(status=overall_status, database=database_status, redis=redis_status)
