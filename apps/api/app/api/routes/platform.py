from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession, IdempotencyKey
from app.models.platform_job import PlatformJob
from app.schemas.operations import OperationsSummary
from app.services.jobs import enqueue_job_signal, get_job, get_job_by_idempotency_key
from app.services.operations import get_operations_summary

router = APIRouter(prefix="/platform", tags=["platform"])


class CreateJobRequest(BaseModel):
    message: str = Field(default="Phase 1 worker is alive", max_length=200)


class JobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    attempt_count: int
    result: dict | None
    error_code: str | None


def to_response(job: PlatformJob) -> JobResponse:
    return JobResponse(
        id=str(job.id),
        job_type=job.job_type,
        status=job.status,
        attempt_count=job.attempt_count,
        result=job.result,
        error_code=job.error_code,
    )


@router.get("/operations", response_model=OperationsSummary)
async def operations(session: DbSession, _user: CurrentUser) -> OperationsSummary:
    return await get_operations_summary(session)


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    payload: CreateJobRequest,
    session: DbSession,
    _user: CurrentUser,
    idempotency_key: IdempotencyKey,
) -> JobResponse:
    existing = await get_job_by_idempotency_key(session, idempotency_key)
    if existing:
        return to_response(existing)

    job = PlatformJob(
        job_type="platform.echo",
        schema_version=1,
        idempotency_key=idempotency_key,
        payload={"message": payload.message},
    )
    session.add(job)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await get_job_by_idempotency_key(session, idempotency_key)
        if existing:
            return to_response(existing)
        raise

    await session.refresh(job)
    await enqueue_job_signal(job.id)
    return to_response(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def read_job(job_id: UUID, session: DbSession, _user: CurrentUser) -> JobResponse:
    job = await get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return to_response(job)
