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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Idempotency-Key",
        "X-Audio-Duration-Ms",
        "X-Correlation-ID",
    ],
)


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
