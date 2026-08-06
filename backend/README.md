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

## Payment/WhatsApp credentials (dashboard Settings)

Razorpay and WhatsApp credentials are per-merchant, not app-wide config — `PUT /api/v1/payments/settings` and `PUT /api/v1/onboarding/whatsapp` (both dashboard-authenticated). Real credentials aren't required to develop against: `payments/adapters/gateway_selector.py` picks a real `RazorpayGateway` only when a merchant's key_id has a genuine `rzp_test_`/`rzp_live_` prefix, otherwise it falls back to `DummyPaymentGateway`, which fabricates a checkout link instead of calling Razorpay and verifies webhooks with the exact same HMAC-SHA256 algorithm Razorpay's real webhooks use. See `IMPLEMENTATION_PLAN.md`'s Phase 5 for the full rationale and how to simulate a webhook locally.

## WhatsApp conversation + ordering webview

`conversation/` handles inbound WhatsApp webhooks (`/api/v1/whatsapp/webhook`) — tenant resolution by `phone_number_id`, message dedup, and intent routing (place order / track order / talk to restaurant). No live WhatsApp Business connection is required to develop against it: `conversation/adapters/whatsapp_client.py`'s `GraphApiWhatsAppSender` always attempts a real Graph API call but treats any failure (dummy token, no live WABA, network error) as a logged no-op rather than an exception, so the whole inbound path is testable regardless.

There's no WhatsApp Flow integration — see `IMPLEMENTATION_PLAN.md`'s Phase 6 for why, and for the webview fallback it uses instead. `ordering_flow/api/router.py` serves that webview's backend: `GET /api/v1/ordering-flow/{merchant_id}/menu` and `POST /api/v1/ordering-flow/{merchant_id}/checkout`, both public/unauthenticated and scoped by `merchant_id` in the URL, since the customer has no dashboard account. Both the webview checkout and the dashboard's test-checkout (Phase 5) go through the same `ordering_flow/domain/checkout.py::perform_checkout`, so they can't drift apart.

## Notifications

`notifications/` subscribes to the `orders/domain/events.py` event bus (async pub-sub, in-process — `OrderPaid`/`OrderConfirmedCOD` → order-confirmed message, `OrderReady` → ready message, `OrderCompleted` → completed message) and sends each via `notifications/adapters/whatsapp_channel.py`'s `WhatsAppNotificationChannel`, built on the same `WhatsAppSender` from the conversation module — so it inherits the same graceful-failure contract: a failed send is logged, never raised, and never blocks the request that published the event. `notifications/wiring.py` registers the subscriptions once at `app.py` import time (not inside `lifespan`, which doesn't run under the tests' `ASGITransport`) and exposes `set_notification_channel`/`get_notification_channel` so tests can swap in a fake channel around anything that would otherwise trigger a real network attempt. See `IMPLEMENTATION_PLAN.md`'s Phase 7 for the full rationale.
