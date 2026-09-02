from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.practice import PracticeNextResponse
from app.services.practice import get_next_silent_practice

router = APIRouter(prefix="/practice", tags=["practice"])


@router.post("/silent/next", response_model=PracticeNextResponse)
async def next_silent_practice(
    user: CurrentUser,
    session: DbSession,
) -> PracticeNextResponse:
    try:
        result = await get_next_silent_practice(session, user)
        await session.commit()
        return result
    except RuntimeError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
