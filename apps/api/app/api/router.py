from fastapi import APIRouter

from app.api.routes import auth, content, health, learning, platform, review

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(platform.router)
api_router.include_router(content.router)
api_router.include_router(learning.router)
api_router.include_router(review.router)
