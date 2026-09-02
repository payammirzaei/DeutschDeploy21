from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.engagement import EngagementSummary
from app.services.engagement import get_engagement_summary

router = APIRouter(prefix="/engagement", tags=["engagement"])


@router.get("/summary", response_model=EngagementSummary)
async def engagement_summary(user: CurrentUser, session: DbSession) -> EngagementSummary:
    return await get_engagement_summary(session, user)
