from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.mastery import RebuildMasteryResult, ReviewHome, ReviewNextResponse
from app.services.mastery import get_next_review, get_review_home, rebuild_mastery

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/home", response_model=ReviewHome)
async def review_home(user: CurrentUser, session: DbSession) -> ReviewHome:
    return await get_review_home(session, user)


@router.post("/next", response_model=ReviewNextResponse)
async def review_next(user: CurrentUser, session: DbSession) -> ReviewNextResponse:
    return await get_next_review(session, user)


@router.post("/rebuild", response_model=RebuildMasteryResult)
async def review_rebuild(user: CurrentUser, session: DbSession) -> RebuildMasteryResult:
    try:
        result = await rebuild_mastery(session, user)
        await session.commit()
        return result
    except RuntimeError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
