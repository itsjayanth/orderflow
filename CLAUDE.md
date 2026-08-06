# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

Backend and frontend scaffolds exist (`backend/`, `frontend/`), following the design in `ARCHITECTURE.md` and the stack decisions in `TECH_STACK.md` — read both before making architecture changes. The scaffold is structural (hexagonal module layout, health check, routing, design-system foundation); most domain logic (entities, state machines, real endpoints) is not implemented yet. Check current repo state before relying on anything beyond this section, since it will go stale as the project is built out.

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
