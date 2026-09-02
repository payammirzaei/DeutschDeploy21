from fastapi import APIRouter

from app.api.routes import (
    auth,
    content,
    health,
    interview_drills,
    learning,
    mock_interview,
    platform,
    practice,
    review,
    speech,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(platform.router)
api_router.include_router(content.router)
api_router.include_router(learning.router)
api_router.include_router(practice.router)
api_router.include_router(interview_drills.router)
api_router.include_router(review.router)
api_router.include_router(speech.router)
api_router.include_router(mock_interview.router)
