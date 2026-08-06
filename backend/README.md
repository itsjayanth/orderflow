# Orderflow Backend

FastAPI backend, modular-by-domain per `ARCHITECTURE.md` and `TECH_STACK.md`. See those docs at the repo root for the system design this scaffold implements.

## Setup

```bash
cd backend
uv sync
cp .env.example .env   # then fill in DATABASE_URL, JWT_SECRET, SECRETS_ENCRYPTION_KEY, etc.
```

Requires a running PostgreSQL instance, with a dev database and a separate test database (tests always run against `<dev-db-name>_test`, hardcoded in `tests/conftest.py`, and drop/recreate its schema on every run — never point `DATABASE_URL` at that database):

```bash
createuser orderflow --login --pwprompt   # or: psql -c "CREATE ROLE orderflow LOGIN PASSWORD 'orderflow';"
createdb orderflow -O orderflow
createdb orderflow_test -O orderflow
```

Generate `SECRETS_ENCRYPTION_KEY` with `uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

## Run

```bash
uv run uvicorn app:app --app-dir src --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Migrations

```bash
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
```

## Checks

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

## Layout

Each `src/<module>/` follows the same hexagonal shape:

- `domain/` — entities, state machines, port interfaces. No framework or DB imports.
- `adapters/` — SQLAlchemy repositories, external API clients (WhatsApp, Razorpay) implementing the domain's ports.
- `api/` — FastAPI routers, request/response schemas.

`src/shared/` holds the cross-cutting kernel: `config.py` (settings), `db.py` (async engine/session), `tenant.py` (`TenantContext`), `security.py` (JWT/Argon2), `encryption.py` (Fernet for secrets at rest), `deps.py` (FastAPI dependencies: `DbSession`, `CurrentTenant`, `CurrentStaffUserId`, resolved from the bearer access token).

`src/dashboard_api/` composes the other modules' routers into the Merchant Dashboard API surface; `src/app.py` is the FastAPI entrypoint.

## Auth

`identity/` implements register/login/refresh/logout/me (`/api/v1/auth/*`). The access token is a short-lived JWT returned in the response body (send it as `Authorization: Bearer <token>`); the refresh token is a longer-lived JWT set as an httpOnly cookie scoped to `/api/v1/auth`, rotated on every `/refresh` call. See `IMPLEMENTATION_PLAN.md`'s Phase 1 for the design rationale.
