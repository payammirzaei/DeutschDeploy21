from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models.learning import ActivityInstance, Attempt, Evaluation
from app.schemas.learning import (
    AttemptIn,
    AttemptResult,
    DayView,
    LearningHome,
    NextActivityResponse,
    StartLearningResult,
)
from app.services.learning import (
    ensure_starter_learning,
    get_day_view,
    get_learning_home,
    get_next_activity,
    submit_attempt,
)
from app.services.mastery import record_attempt_evidence

router = APIRouter(prefix="/learning", tags=["learning"])


@router.post("/start", response_model=StartLearningResult)
async def start_learning(user: CurrentUser, session: DbSession) -> StartLearningResult:
    try:
        result = await ensure_starter_learning(session, user)
        await session.commit()
        return result
    except (RuntimeError, ValueError) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get("/home", response_model=LearningHome)
async def learning_home(user: CurrentUser, session: DbSession) -> LearningHome:
    return await get_learning_home(session, user)


@router.get("/days/{day_number}", response_model=DayView)
async def learning_day(
    day_number: int,
    user: CurrentUser,
    session: DbSession,
) -> DayView:
    try:
        return await get_day_view(session, user, day_number)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/days/{day_number}/next", response_model=NextActivityResponse)
async def next_activity(
    day_number: int,
    user: CurrentUser,
    session: DbSession,
) -> NextActivityResponse:
    try:
        result = await get_next_activity(session, user, day_number)
        await session.commit()
        return result
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post("/instances/{instance_id}/attempts", response_model=AttemptResult)
async def create_attempt(
    instance_id: UUID,
    payload: AttemptIn,
    user: CurrentUser,
    session: DbSession,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=180),
) -> AttemptResult:
    try:
        result = await submit_attempt(
            session,
            user,
            instance_id,
            idempotency_key,
            payload,
        )
        attempt = await session.get(Attempt, result.attempt_id)
        evaluation = await session.get(Evaluation, result.evaluation_id)
        instance = await session.get(ActivityInstance, instance_id)
        if attempt is None or evaluation is None or instance is None:
            raise RuntimeError("Submitted attempt could not be projected into mastery")
        await record_attempt_evidence(session, user, attempt, evaluation, instance)
        await session.commit()
        return result
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
