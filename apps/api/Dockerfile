FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app/apps/api

COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /uvx /bin/
COPY apps/api/pyproject.toml ./
RUN uv sync --no-dev

COPY apps/api/alembic.ini ./
COPY apps/api/alembic ./alembic
COPY apps/api/app ./app
COPY content /app/content

ENV PATH="/app/apps/api/.venv/bin:$PATH"
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
