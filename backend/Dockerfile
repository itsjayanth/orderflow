# uv-managed FastAPI backend. Single image runs both the API and the
# abandoned-order-sweep scheduler (in-process via app.py's lifespan,
# shared/scheduler.py) -- there's no separate worker process to build,
# which matches Render's free tier (no free background-worker service type).
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Dependencies first so this layer only rebuilds when pyproject.toml/uv.lock
# change, not on every source edit.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

EXPOSE 8000

# Render sets $PORT; uvicorn must bind to it, not a hardcoded port. Shell
# form so the variable expands at container start, not build time.
CMD uvicorn app:app --app-dir src --host 0.0.0.0 --port ${PORT:-8000}
