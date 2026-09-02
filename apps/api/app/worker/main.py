import asyncio
from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as redis
import structlog
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionFactory
from app.models.platform_job import PlatformJob
from app.services.speech_processing import process_speech_transcription

configure_logging()
logger = structlog.get_logger()
settings = get_settings()


async def claim_fallback_job() -> UUID | None:
    async with SessionFactory() as session:
        result = await session.execute(
            select(PlatformJob.id)
            .where(PlatformJob.status == "queued")
            .order_by(PlatformJob.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def _execute_job(job: PlatformJob, session) -> dict:
    if job.job_type == "platform.echo":
        await asyncio.sleep(0.15)
        return {
            "echo": job.payload.get("message"),
            "worker": "deutschdeploy21-worker",
            "schema_version": job.schema_version,
        }
    if job.job_type == "speech.transcribe":
        return await process_speech_transcription(session, job)
    raise ValueError(f"Unsupported job type: {job.job_type}")


async def process_job(job_id: UUID) -> None:
    async with SessionFactory() as session:
        job = await session.get(PlatformJob, job_id, with_for_update=True)
        if not job or job.status != "queued":
            return

        job.status = "running"
        job.started_at = datetime.now(UTC)
        job.attempt_count += 1
        await session.commit()

        try:
            job.result = await _execute_job(job, session)
            job.status = "succeeded"
            job.finished_at = datetime.now(UTC)
            job.error_code = None
            job.error_message = None
            await session.commit()
            logger.info("job_succeeded", job_id=str(job.id), job_type=job.job_type)
        except Exception as exc:
            job.status = "failed"
            job.finished_at = datetime.now(UTC)
            job.error_code = "WORKER_JOB_FAILED"
            job.error_message = str(exc)[:1000]
            await session.commit()
            logger.exception("job_failed", job_id=str(job.id), job_type=job.job_type)


async def run() -> None:
    logger.info("worker_started", queue=settings.redis_job_queue)
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        while True:
            job_id: UUID | None = None
            try:
                item = await client.brpop(settings.redis_job_queue, timeout=5)
                if item:
                    _, raw_id = item
                    job_id = UUID(raw_id)
            except (redis.RedisError, ValueError) as exc:
                logger.warning("queue_receive_failed", error=type(exc).__name__)

            if job_id is None:
                job_id = await claim_fallback_job()
            if job_id is not None:
                await process_job(job_id)
            else:
                await asyncio.sleep(1)
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(run())
