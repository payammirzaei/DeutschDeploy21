from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.platform_job import PlatformJob


async def get_job(session: AsyncSession, job_id: UUID) -> PlatformJob | None:
    return await session.get(PlatformJob, job_id)


async def get_job_by_idempotency_key(
    session: AsyncSession, idempotency_key: str
) -> PlatformJob | None:
    result = await session.execute(
        select(PlatformJob).where(PlatformJob.idempotency_key == idempotency_key)
    )
    return result.scalar_one_or_none()


async def enqueue_job_signal(job_id: UUID) -> bool:
    settings = get_settings()
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.lpush(settings.redis_job_queue, str(job_id))
        return True
    except redis.RedisError:
        return False
    finally:
        await client.aclose()
