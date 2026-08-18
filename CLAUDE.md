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

Orderflow is a WhatsApp-based ordering system for independent restaurants (MVP phase, pilot target: a small cluster in Bangalore). Read the full brief at `docs/project-brief.txt` before making product/architecture decisions — key points to keep in mind:

- **Two sides**: a customer-facing WhatsApp chat flow (browse catalog → cart → order summary → payment link → confirmation → status updates), and a merchant-facing web dashboard (orders list/detail, manual status updates, menu/catalog management). No native mobile app for merchants — responsive web is sufficient.
- **Core pipeline**: WhatsApp conversation state → order object → payment status → merchant app order list. An order should appear in the merchant dashboard within seconds of payment confirmation.
- **Integrations implied by the brief**: WhatsApp Cloud API (via a Business Solution Provider) for chat/catalog/template messages; Razorpay (or similar) payment links with a webhook for payment confirmation.
- **Order status flow**: New → Preparing → Ready → Completed, staff-driven from the merchant app. At minimum, the "Ready"/"Completed" transition must trigger a WhatsApp message back to the customer.
- **Explicitly out of scope for MVP**: POS/KDS integration (Petpooja/UrbanPiper — planned Phase 2), kitchen printer auto-ticketing, loyalty/broadcast marketing, multi-outlet management, multi-user roles/permissions, free-text AI chatbot ordering (use structured/guided flows instead), any non-restaurant vertical, native mobile apps.
- **Data model guidance from the brief**: keep the order object "POS-integration-friendly" — don't bake in app-only assumptions — since Phase 2 needs to slot in a Petpooja order-injection API without re-architecting the order model. Per-order data: order ID, customer name/phone, items + quantities, total, payment status, order status, timestamps.

When scaffolding new code in this repo, favor structure that matches this brief (e.g., a clean separation between the WhatsApp conversation/webhook layer, the order/payment domain model, and the merchant dashboard) rather than inventing an unrelated architecture.

## Order flow — how it actually works today

This section documents the real, current order-flow implementation, traced through the code (not the aspirational design). It gets stale as the code changes — re-verify against the file paths below before trusting specifics.

**Tech stack**: Python 3.12 / FastAPI backend, SQLAlchemy 2.0 (async) on PostgreSQL, modular-by-domain under `backend/src/`. React + TypeScript frontend (Vite). WhatsApp provider is **Meta's WhatsApp Cloud API directly** (not Twilio or another BSP). Payments via **Razorpay**. No queueing/worker system for order intake — webhook handlers run inline in the FastAPI request; a lightweight APScheduler job handles the one background sweep that exists (abandoned-order cancellation).

### 1. WhatsApp order intake

A customer messages the restaurant's WhatsApp number. Meta forwards it to `POST /api/v1/whatsapp/webhook` (`backend/src/conversation/api/router.py`), which always answers 200 immediately (required so Meta doesn't retry-storm). Verification for Meta's handshake is `GET` on the same route.

Inside, the app: matches the incoming WhatsApp phone number ID to a merchant, checks the merchant has finished onboarding, finds-or-creates the customer by phone number, and de-duplicates (WhatsApp can redeliver the same message).

Then it branches on intent (`backend/src/conversation/domain/intents.py`):
- Greeting/plain text → sends a button menu ("Place order" / "Track order" / "Talk to restaurant").
- "Place order" → if the merchant has a native **WhatsApp Flow** configured (an in-chat ordering form), opens it; otherwise sends a link to a plain web ordering page. Both paths converge on the same checkout logic.
- Flow completed (items, delivery/pickup, address, payment method chosen) → parsed and turned into a real order, then a confirmation/payment-link message is sent back.
- "Track order" → replies with the latest order's status.

The in-chat Flow's screen-by-screen data exchange is a separate, Meta-spec-encrypted (RSA/AES) endpoint: `POST /api/v1/whatsapp/flows/{merchant_id}/data-exchange` (`backend/src/flows/api/router.py`). The web fallback lives under `backend/src/ordering_flow/api/router.py` + `frontend/src/features/ordering/`.

Outbound WhatsApp sends go through `backend/src/conversation/adapters/whatsapp_client.py` (`GraphApiWhatsAppSender`), posting straight to `graph.facebook.com` using each merchant's own stored access token — sends are best-effort (failures are logged, never raised, so webhook handling always completes).

**Key files**: `conversation/api/router.py`, `conversation/domain/{webhook_parser,handler,intents}.py`, `conversation/adapters/whatsapp_client.py`, `flows/api/router.py`, `flows/domain/{encryption,menu_order,images}.py`, `ordering_flow/api/router.py`, `ordering_flow/domain/checkout.py`.

**Gaps**: none obviously stubbed — intake, both ordering paths, and checkout appear fully wired.

### 2. Customer & address handling

Customers are identified by **WhatsApp phone number**, scoped per merchant (multi-tenant — the same phone number is a different customer row per restaurant). `Customer` (`backend/src/customers/domain/models.py`) holds a UUID id, a human-friendly sequential `customer_number`, `whatsapp_number`, optional `display_name`, and an optional separate `default_contact_phone` for delivery calls. `CustomerRepository.find_or_create()` is idempotent on `(merchant_id, whatsapp_number)` and runs on every inbound message — so a customer record exists from first contact, before any order.

Address capture has **no WhatsApp location-pin support** (not implemented anywhere in the code, despite unused `geo_lat`/`geo_long` columns sitting on the model). Two real paths, both ending in the same `perform_checkout()`:
- **Web ordering page**: customer types the address into a form (line1/line2/landmark/city/pincode). A **new** `Address` row is created every time, even for a returning customer.
- **Native WhatsApp Flow**: if the customer previously saved an address and confirms "same" in the Flow, the existing `Address` row is reused (`AddressRepository.get_primary_for_customer`); otherwise a new one is created, same as the web path.

Storage: Postgres, `customers` and `addresses` tables (`backend/src/customers/domain/models.py`), accessed via `CustomerRepository` / `AddressRepository` in `backend/src/customers/adapters/repository.py`.

**Gaps**: no location-pin capture; `geo_lat`/`geo_long` are dead columns; no update/delete API for saved addresses (only lookup/list).

### 3. Order management

Two coupled state machines (`backend/src/orders/domain/state_machine.py`), not one linear list:

- **`payment_status`**: `awaiting_payment → paid | payment_failed | cancelled`; `payment_failed → awaiting_payment` (retry); `cod_pending → cod_collected` for cash orders.
- **`fulfillment_status`** — this is the brief's New→Preparing→Ready→Completed, matched exactly, plus `cancelled` from any non-terminal state: `new → preparing → ready → completed`.

The two are gated together: `fulfillment_status` stays unset until `payment_status` reaches `paid` or `cod_pending`, so kitchen staff never see an order without a valid payment path. A `cancelled` payment status force-cancels fulfillment too.

Triggers:
- `awaiting_payment` / `cod_pending` — set at order creation in `ordering_flow/domain/checkout.py`.
- `paid` / `payment_failed` — **Razorpay webhook**, `POST /api/v1/payments/webhook/razorpay/{merchant_id}` (`payments/api/router.py`), signature-verified.
- `cancelled` (payment side) — automated timeout: `shared/scheduler.py`'s `sweep_abandoned_orders`, an APScheduler job that cancels orders stuck too long in `awaiting_payment`.
- `preparing` / `ready` / `completed` / `cancelled` (fulfillment side) — **manual staff action only**, via `PATCH /api/v1/orders/{order_id}/fulfillment-status` (`orders/api/router.py`), requiring a logged-in staff user. Each transition fires an in-process event that `notifications/wiring.py` turns into a WhatsApp status update to the customer.

**Dashboard is real, not scaffolding**: `frontend/src/features/orders/` has a working orders list, order detail page, and status-transition UI (`statusTransitions.ts` mirrors the backend's allowed transitions so the UI only offers legal moves — server still enforces it). `backend/src/dashboard_api/` is just a thin router aggregator with no logic of its own; the real logic lives in `orders/`, `payments/`, `notifications/`, etc.

**Gaps**: `cod_collected` is a defined payment state with **no way to reach it** — no endpoint or job transitions into it. `payments/api/dashboard_router.py` has a `/test-checkout` endpoint explicitly labeled in-code as a staff-facing stand-in for the real WhatsApp flow (useful for testing, not customer-facing).

### 4. Pricing

Entirely static, and minimal — **no tax, delivery fee, or discount/coupon logic exists anywhere** in the codebase (confirmed by grep; zero hits for coupon/discount/promo/delivery-fee concepts).

In `ordering_flow/domain/checkout.py`'s `perform_checkout()`, each cart line's price is read from the catalog and frozen as `price_snapshot` on the order item (so later menu edits don't retroactively change past orders). `OrderRepository.create()` (`orders/adapters/repository.py`) computes `line_total = price_snapshot * quantity`, `subtotal = sum(line_totals)`, and **`total = subtotal`** — a straight passthrough, no additive/subtractive step at all.

`MenuItem.price` (`catalog/domain/models.py`) is a single flat `Numeric(10,2)` column — no variants, modifiers, or rules engine. `Order` stores `subtotal`, `total`, `currency` (default `"INR"`) but has no `tax_amount`, `delivery_fee`, or `discount_amount` columns — there's nowhere to even persist those values if the logic existed.

**Gaps**: taxes, delivery/shipping fees, and discounts/coupons are completely unimplemented — no schema fields, no calculation code, no API params, anywhere in checkout, orders, catalog, or payments.

**Key files**: `ordering_flow/domain/checkout.py` (`perform_checkout`), `orders/adapters/repository.py` (total computation), `orders/domain/models.py` (`Order`, `OrderItem`), `catalog/domain/models.py` (`MenuItem.price`).
