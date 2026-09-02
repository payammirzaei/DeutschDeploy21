from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.interview_drills import InterviewDrillNextResponse
from app.services.interview_drills import get_next_interview_drill

router = APIRouter(prefix="/interview-drills", tags=["interview-drills"])


@router.post("/next", response_model=InterviewDrillNextResponse)
async def next_interview_drill(
    user: CurrentUser,
    session: DbSession,
) -> InterviewDrillNextResponse:
    try:
        result = await get_next_interview_drill(session, user)
        await session.commit()
        return result
    except (RuntimeError, ValueError) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
