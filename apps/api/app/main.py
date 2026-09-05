from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.bootstrap import ensure_bootstrap_user

configure_logging()
logger = structlog.get_logger()
settings = get_settings()

# Local/LAN phone testing often uses http://<lan-ip>:3000 while WEB_ORIGIN stays
# localhost. In development/test, also accept private-network Origins.
_DEV_LAN_ORIGIN_REGEX = (
    r"https?://("
    r"localhost|127\.0\.0\.1|"
    r"10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}|"
    r"100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}"
    r")(?::\d+)?$"
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await ensure_bootstrap_user()
    yield


app = FastAPI(
    title="DeutschDeploy21 API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.app_env != "production" else None,
    openapi_url="/api/openapi.json",
)

_cors_kwargs: dict = {
    "allow_origins": settings.web_origins,
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    "allow_headers": [
        "Content-Type",
        "Idempotency-Key",
        "X-Audio-Duration-Ms",
        "X-Correlation-ID",
    ],
}
if settings.app_env in {"development", "test"}:
    _cors_kwargs["allow_origin_regex"] = _DEV_LAN_ORIGIN_REGEX

app.add_middleware(CORSMiddleware, **_cors_kwargs)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
    finally:
        structlog.contextvars.clear_contextvars()


app.include_router(api_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "deutschdeploy21-api", "status": "ok"}
