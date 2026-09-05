from datetime import UTC, datetime, timedelta

import redis.asyncio as redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.platform_job import PlatformJob
from app.models.speech import ProviderInvocation
from app.schemas.operations import OperationsSummary

STALE_QUEUE_SECONDS = 120
REDIS_BACKLOG_THRESHOLD = 20


def build_alert_codes(
    *,
    oldest_queued_seconds: int | None,
    redis_queue_depth: int | None,
    failed_jobs_24h: int,
    provider_failures_24h: int,
) -> list[str]:
    alerts: list[str] = []
    if redis_queue_depth is None:
        alerts.append("redis_queue_unavailable")
    elif redis_queue_depth > REDIS_BACKLOG_THRESHOLD:
        alerts.append("redis_queue_backlog")
    if oldest_queued_seconds is not None and oldest_queued_seconds > STALE_QUEUE_SECONDS:
        alerts.append("worker_queue_stale")
    if failed_jobs_24h:
        alerts.append("worker_failures_24h")
    if provider_failures_24h:
        alerts.append("provider_failures_24h")
    return alerts


async def _redis_queue_depth() -> int | None:
    settings = get_settings()
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        return int(await client.llen(settings.redis_job_queue))
    except redis.RedisError:
        return None
    finally:
        await client.aclose()


async def get_operations_summary(session: AsyncSession) -> OperationsSummary:
    now = datetime.now(UTC)
    since = now - timedelta(hours=24)

    queued_jobs = int(
        await session.scalar(
            select(func.count(PlatformJob.id)).where(PlatformJob.status == "queued")
        )
        or 0
    )
    running_jobs = int(
        await session.scalar(
            select(func.count(PlatformJob.id)).where(PlatformJob.status == "running")
        )
        or 0
    )
    failed_jobs_24h = int(
        await session.scalar(
            select(func.count(PlatformJob.id)).where(
                PlatformJob.status == "failed",
                PlatformJob.finished_at >= since,
            )
        )
        or 0
    )
    succeeded_jobs_24h = int(
        await session.scalar(
            select(func.count(PlatformJob.id)).where(
                PlatformJob.status == "succeeded",
                PlatformJob.finished_at >= since,
            )
        )
        or 0
    )
    oldest_queued_at = await session.scalar(
        select(func.min(PlatformJob.created_at)).where(PlatformJob.status == "queued")
    )
    oldest_queued_seconds = (
        max(0, int((now - oldest_queued_at).total_seconds())) if oldest_queued_at else None
    )

    provider_invocations_24h = int(
        await session.scalar(
            select(func.count(ProviderInvocation.id)).where(ProviderInvocation.created_at >= since)
        )
        or 0
    )
    provider_failures_24h = int(
        await session.scalar(
            select(func.count(ProviderInvocation.id)).where(
                ProviderInvocation.created_at >= since,
                ProviderInvocation.status == "failed",
            )
        )
        or 0
    )
    estimated_cost = int(
        await session.scalar(
            select(func.coalesce(func.sum(ProviderInvocation.estimated_cost_microusd), 0)).where(
                ProviderInvocation.created_at >= since
            )
        )
        or 0
    )
    redis_queue_depth = await _redis_queue_depth()
    alert_codes = build_alert_codes(
        oldest_queued_seconds=oldest_queued_seconds,
        redis_queue_depth=redis_queue_depth,
        failed_jobs_24h=failed_jobs_24h,
        provider_failures_24h=provider_failures_24h,
    )

    return OperationsSummary(
        status="attention" if alert_codes else "ok",
        queued_jobs=queued_jobs,
        running_jobs=running_jobs,
        failed_jobs_24h=failed_jobs_24h,
        succeeded_jobs_24h=succeeded_jobs_24h,
        oldest_queued_seconds=oldest_queued_seconds,
        redis_queue_depth=redis_queue_depth,
        provider_invocations_24h=provider_invocations_24h,
        provider_failures_24h=provider_failures_24h,
        estimated_provider_cost_microusd_24h=estimated_cost,
        alert_codes=alert_codes,
    )
