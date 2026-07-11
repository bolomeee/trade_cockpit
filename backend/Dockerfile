FROM python:3.12.8-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN mkdir -p /app/data

ENV PATH="/app/.venv/bin:$PATH" \
    DATABASE_URL="sqlite:////app/data/prod.db"

EXPOSE 8000

FROM base AS development

# Install the locked development dependency group inside the image.  The source
# tree is mounted selectively by the Compose dev profile, so this venv remains
# container-owned and never depends on a developer's local uv installation.
RUN uv sync --frozen --no-install-project

CMD ["sh", "-c", "uv sync --frozen --no-install-project && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]

FROM base AS production

RUN uv sync --frozen --no-dev --no-install-project

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
