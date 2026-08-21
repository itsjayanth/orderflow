# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

Backend and frontend scaffolds exist (`backend/`, `frontend/`), following the design in `ARCHITECTURE.md` and the stack decisions in `TECH_STACK.md` — read both before making architecture changes. The scaffold is structural (hexagonal module layout, health check, routing, design-system foundation); most domain logic (entities, state machines, real endpoints) is not implemented yet. `IMPLEMENTATION_PLAN.md` breaks the remaining work into ordered phases (Identity → Catalog → Customers → Orders → Payments → WhatsApp → Notifications → Onboarding) — when picking up implementation work, check it first for what phase is next and what a phase's definition of done looks like. Check current repo state before relying on anything beyond this section, since it will go stale as the project is built out.

### Backend (`backend/`)

Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, `uv` for dependency management. Modular-by-domain under `backend/src/<module>/{domain,adapters,api}` (identity, onboarding, conversation, ordering_flow, catalog, customers, orders, payments, notifications, dashboard_api), plus a `shared/` kernel (config, DB session, `TenantContext`, JWT/Argon2, Fernet encryption). See `backend/README.md`.

```bash
cd backend
uv sync
uv run uvicorn app:app --app-dir src --reload --port 8000   # run
uv run pytest                                                 # test
uv run ruff check .                                           # lint
uv run mypy src                                                # type-check
uv run alembic revision --autogenerate -m "message" && uv run alembic upgrade head   # migrate
```

### Frontend (`frontend/`)

React 18 + TypeScript on Vite, Tailwind CSS + shadcn/ui (hand-placed under `src/components/ui/` — the shadcn CLI's registry fetch may be network-blocked in sandboxed environments), TanStack Query for server state, Zustand for client-only UI state, React Router, React Hook Form + Zod, Biome for lint/format. Feature-sliced under `frontend/src/features/`. See `frontend/README.md`.

```bash
cd frontend
npm install
npm run dev         # run (localhost:5173)
npm run test        # vitest
npm run lint         # biome check .
npm run typecheck
npm run build
```

## Product context (from `docs/project-brief.txt`)

Orderflow is a WhatsApp-based ordering system for independent restaurants (MVP phase, pilot target: a small cluster in Bangalore). Read the full brief before making product/architecture decisions.

- Two sides: customer-facing WhatsApp chat flow (browse → cart → order summary → payment link → confirmation → status updates), and a merchant-facing web dashboard (orders, manual status updates, menu/catalog management). No native mobile app.
- Core pipeline: WhatsApp conversation state → order object → payment status → merchant app order list, within seconds of payment confirmation.
- Integrations implied by the brief: WhatsApp Cloud API (via a BSP) for chat/catalog/templates; Razorpay (or similar) payment links with a webhook.
- Order status flow: New → Preparing → Ready → Completed, staff-driven; Ready/Completed must trigger a WhatsApp message to the customer.
- Out of scope for MVP: POS/KDS integration (Petpooja/UrbanPiper — Phase 2), kitchen printer auto-ticketing, loyalty/broadcast marketing, multi-outlet management, multi-user roles, free-text AI chatbot ordering, non-restaurant verticals, native mobile apps.
- Data model guidance: keep the order object "POS-integration-friendly" (Phase 2 needs to slot in a Petpooja order-injection API without re-architecting). Per-order data: order ID, customer name/phone, items + quantities, total, payment status, order status, timestamps.

Favor structure that matches this brief (clean separation between the WhatsApp conversation/webhook layer, the order/payment domain model, and the merchant dashboard) over inventing an unrelated architecture.

## Order flow — how it actually works today

Traced through the actual code, not the aspirational design — it goes stale as the code changes, so re-verify specifics before trusting them. Tech: FastAPI + SQLAlchemy (async)/Postgres backend, React/Vite frontend, **Meta's WhatsApp Cloud API directly** (not Twilio/another BSP), **Razorpay** for payments. No queue/worker — webhook handlers run inline in the FastAPI request; the only background job is an APScheduler sweep that cancels abandoned orders.

**1. WhatsApp intake** — `POST /api/v1/whatsapp/webhook` (`conversation/api/router.py`) always returns 200 immediately (Meta retry-storms otherwise); `GET` on the same route handles Meta's verification handshake. Matches phone number ID → merchant, finds-or-creates customer, de-dupes redelivered messages, then branches on intent (`conversation/domain/intents.py`): greeting → button menu; "Place order" → native WhatsApp Flow if configured, else a web ordering link, both converging on the same checkout logic; "Track order" → latest status. The Flow's screen-by-screen exchange is a separate Meta-spec-encrypted (RSA/AES) endpoint, `POST /api/v1/whatsapp/flows/{merchant_id}/data-exchange` (`flows/api/router.py`); the web fallback is `ordering_flow/api/router.py` + `frontend/src/features/ordering/`. Outbound sends (`conversation/adapters/whatsapp_client.py`) post directly to `graph.facebook.com` with each merchant's own token and are best-effort — failures are logged, never raised. Nothing here is obviously stubbed.

**2. Customers & addresses** — Identified by WhatsApp phone number, scoped per merchant (multi-tenant: same number = different customer row per restaurant). `CustomerRepository.find_or_create()` (`customers/adapters/repository.py`) is idempotent on `(merchant_id, whatsapp_number)` and runs on every inbound message, so a customer row exists before any order. **No WhatsApp location-pin support** anywhere, despite dead `geo_lat`/`geo_long` columns on the model. Web ordering page always creates a **new** `Address` row, even for returning customers; the native Flow reuses the saved address (`AddressRepository.get_primary_for_customer`) if the customer confirms "same," otherwise also creates new. No update/delete API for saved addresses (lookup/list only).

**3. Order management** — Two coupled state machines (`orders/domain/state_machine.py`), not one linear list:
- `payment_status`: `awaiting_payment → paid | payment_failed | cancelled`; `payment_failed → awaiting_payment` (retry); `cod_pending → cod_collected` for cash — **but `cod_collected` is unreachable: no endpoint or job ever transitions into it.**
- `fulfillment_status`: `new → preparing → ready → completed`, plus `cancelled` from any non-terminal state (matches the brief exactly).

Gated together: `fulfillment_status` stays unset until `payment_status` reaches `paid` or `cod_pending`, so kitchen staff never see an order without a valid payment path; a `cancelled` payment status force-cancels fulfillment too. Payment-side transitions come from the Razorpay webhook (`POST /api/v1/payments/webhook/razorpay/{merchant_id}`, signature-verified) or the abandoned-order sweep; fulfillment-side transitions are manual-staff-only via `PATCH /api/v1/orders/{order_id}/fulfillment-status`, each firing an event that `notifications/wiring.py` turns into a WhatsApp status update. The dashboard (`frontend/src/features/orders/`) is a real working orders list/detail/status-transition UI, not scaffolding — `statusTransitions.ts` mirrors backend-allowed transitions client-side (server still enforces). `payments/api/dashboard_router.py`'s `/test-checkout` endpoint is explicitly a staff-facing stand-in for the real WhatsApp flow, not customer-facing.

**4. Pricing** — Entirely static and minimal: **no tax, delivery fee, or discount/coupon logic anywhere** (zero grep hits for coupon/discount/promo/delivery-fee), and no schema fields to even persist such values (`Order` has `subtotal`/`total`/`currency` only). `perform_checkout()` (`ordering_flow/domain/checkout.py`) freezes each cart line's catalog price as `price_snapshot`; `OrderRepository.create()` computes `line_total = price_snapshot * quantity`, `subtotal = sum(line_totals)`, and `total = subtotal` — a straight passthrough. `MenuItem.price` (`catalog/domain/models.py`) is a single flat `Numeric(10,2)` — no variants, modifiers, or rules engine.
