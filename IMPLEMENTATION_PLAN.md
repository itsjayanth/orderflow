# Orderflow — Implementation Plan (MVP)

Turns the scaffold in `backend/` and `frontend/` (structural only — see their READMEs) into the working MVP described in `docs/project-brief.txt`, following the design in `ARCHITECTURE.md` and the stack in `TECH_STACK.md`. Phases are ordered so each one ends in something runnable and testable, and each depends only on phases before it — no phase requires later work to demo.

Every phase follows the same shape:
1. **Migration** — SQLAlchemy models + `alembic revision --autogenerate`, hand-reviewed.
2. **Domain** — entities/state machines in `<module>/domain/`, pure Python, no FastAPI/SQLAlchemy imports.
3. **Adapters** — repository (tenant-scoped, per `shared/tenant.py`) in `<module>/adapters/`.
4. **API** — Pydantic schemas + router in `<module>/api/`, registered in `dashboard_api/api/router.py` or `app.py` as appropriate.
5. **Backend tests** — repository test against real Postgres, endpoint test via `httpx.AsyncClient`.
6. **Frontend** — types (from OpenAPI or hand-written until codegen is wired, see Phase 1), TanStack Query hooks in `shared/hooks/` or feature-local, page/components in `features/<feature>/`.
7. **Frontend tests** — Vitest + RTL for the page's core interaction.

Each phase ends with a **Definition of done** — the concrete thing you can click through or curl.

---

## Phase 0 — already done

Scaffold only: FastAPI app boots, health check, hexagonal folders per module, Alembic wired to `Base.metadata`, React app boots with routing/Tailwind/shadcn foundation, TanStack Query wired to a live health check. Nothing here is business logic yet.

---

## Phase 1 — Identity & Access + tenant plumbing ✅ done

Everything downstream is tenant-scoped and dashboard-authenticated, so this unblocks every other phase.

Implemented as described below, with one upgrade beyond the original plan: the refresh token is delivered as an httpOnly cookie scoped to `/api/v1/auth` (rotated on every `/refresh` call) rather than returned in the JSON body, matching `TECH_STACK.md`'s "refresh token in an httpOnly cookie, not localStorage" intent from the start rather than retrofitting it later. `POST /logout` (not in the original plan) clears the cookie.

**Backend**
- `identity/domain/models.py`: `Merchant`, `StaffUser` SQLAlchemy models (fields per `ARCHITECTURE.md` §1). Add `Merchant.onboarding_status` as a plain string column now (enum values from §5); the state machine logic itself lands in Phase 8 — for now everything created here defaults to `"live"` so downstream phases aren't blocked on onboarding being built.
- `identity/adapters/repository.py`: `MerchantRepository`, `StaffUserRepository`, both taking `TenantContext` (except merchant creation/lookup-by-email, which precedes tenant resolution).
- `identity/domain/auth.py`: register (hash password via `shared/security.py`), login (verify + issue access/refresh JWT), refresh.
- `identity/api/router.py`: `POST /register`, `POST /login`, `POST /refresh`, `GET /me`.
- `shared/deps.py` (new): FastAPI dependency `get_tenant_context` — decodes the access token (from `Authorization: Bearer` for now; httpOnly refresh cookie wiring can follow once the frontend needs it), resolves `StaffUser` → `TenantContext`. Every other module's router depends on this from here on.
- Migration: `merchants`, `staff_users` tables.
- Tests: register → login → `GET /me` round trip; a request with no/invalid token gets 401; cross-tenant access via a forged token to another merchant's resource is rejected once Phase 2 gives us something to test it against.

**Frontend**
- `shared/api/types.ts` (hand-written for now — swap to generated types once the backend has enough surface for `openapi-typescript` to be worth wiring, suggest revisiting at end of Phase 3): `Merchant`, `StaffUser`, `AuthResponse`.
- `features/auth/`: `LoginPage.tsx` (React Hook Form + Zod), `useAuth.ts` (TanStack Query mutation for login, stores access token — in memory per `TECH_STACK.md`, e.g. a small non-Zustand module-level store or a `useAuthStore` if that reads cleaner).
- `shared/api/client.ts`: attach `Authorization` header from the auth store; on 401, clear auth state and redirect to `/login`.
- Route guard: wrap the existing `Layout` route tree so unauthenticated users are redirected to `/login`.

**Definition of done**: `POST /register` then `POST /login` returns a token; the dashboard shows a login form, and hitting `/` unauthenticated redirects to it; logging in lands back on the (still-placeholder) dashboard home.

---

## Phase 2 — Catalog (MenuItem) ✅ done

Simplest entity, no dependents — good place to prove the full-stack pattern before tackling the harder domains. Implemented as described below (soft-delete via `is_available` toggle rather than a separate delete endpoint, matching the plan).

**Backend**
- `catalog/domain/models.py`: `MenuItem` (per `ARCHITECTURE.md` §1).
- `catalog/adapters/repository.py`: `MenuItemRepository` (list by merchant, filter `is_available`, create, update, soft-delete via `is_available=false` rather than hard delete — matches "availability toggle" in the brief).
- `catalog/api/router.py`: `GET /api/v1/catalog/items`, `POST /api/v1/catalog/items`, `PATCH /api/v1/catalog/items/{id}`, all behind `get_tenant_context`.
- Migration: `menu_items`.
- Tests: create/list/update round trip; a second merchant's token can't see or edit the first merchant's items (the concrete tenant-isolation test flagged in Phase 1).

**Frontend**
- `features/catalog/`: `useMenuItems.ts` (query), `useCreateMenuItem.ts` / `useUpdateMenuItem.ts` (mutations, invalidate the list query on success).
- `CatalogPage.tsx`: replace the placeholder with a table (item, category, price, availability toggle) + an "Add item" form (RHF + Zod, shadcn `Input`/`Select`/`Switch` — add those primitives to `components/ui/` following `button.tsx`'s pattern).
- Test: rendering the table from a mocked query client; submitting the add-item form calls the mutation with the right payload.

**Definition of done**: log in, add a menu item in the dashboard, see it appear in the list without a page reload, toggle its availability.

---

## Phase 3 — Customers & Addresses ✅ done

Implemented as described below. Phases 2 and 3 were built in parallel (independent domains, no shared files once the API routers and UI pages already existed as placeholders) and merged together; the combined `menu_items`/`customers`/`addresses` migration was generated once after merging, rather than per-agent, to avoid a branching migration history.

**Backend**
- `customers/domain/models.py`: `Customer`, `Address`.
- `customers/adapters/repository.py`: `CustomerRepository` (find-or-create by `merchant_id` + `whatsapp_number` — this is the method Phase 6's Conversation Handler will call), `AddressRepository`.
- `customers/api/router.py`: `GET /api/v1/customers`, `GET /api/v1/customers/{id}` (with addresses) — read-only for the dashboard in MVP; writes only happen from the WhatsApp ordering flow (Phase 6).
- Migration: `customers`, `addresses`.
- Tests: find-or-create idempotency (same phone number twice doesn't duplicate); address CRUD scoped to a customer.

**Frontend**
- `features/customers/`: `useCustomers.ts`.
- `CustomersPage.tsx`: replace placeholder with a read-only list (name, phone, last order date) — detail view can wait, it's not on the brief's critical path.

**Definition of done**: `useCustomerService.findOrCreate()` (backend, exercised by a test) returns the same customer for the same phone number across two calls; dashboard Customers page lists whatever's in the table (empty until Phase 6 seeds it, or seed manually for now).

---

## Phase 4 — Orders domain (entities, state machines, dashboard CRUD) ✅ done

The two state machines from `ARCHITECTURE.md` §7 are the highest-risk piece of logic in the whole system — build and test them in isolation before wiring payments or WhatsApp to them. Implemented as described below; `orders/domain/state_machine.py` is exhaustively unit-tested (85 cases: every legal transition in both tables plus every illegal `(from, to)` combination across the full state space, no DB involved) before anything else was built on top of it.

**Backend**
- `orders/domain/models.py`: `Order`, `OrderItem`, `OrderStatusEvent`.
- `orders/domain/state_machine.py`: two explicit transition tables (`PAYMENT_TRANSITIONS`, `FULFILLMENT_TRANSITIONS` per §7a/§7b) as plain data (`dict[tuple[str,str], bool]` or similar) with a `transition(order, to_status) -> Order` function per machine that raises on an illegal transition. Unit-test this file exhaustively — every row in both tables, plus every illegal transition — with no DB involved.
- `orders/domain/events.py`: a minimal in-process pub-sub (`subscribe(event_type, handler)` / `publish(event)`) — this is what Notification Service (Phase 7) and, later, Phase 2's POS seam hang off. Keep it dead simple (a dict of lists + synchronous dispatch); no message broker needed at this scale per `TECH_STACK.md`.
- `orders/adapters/repository.py`: `OrderRepository` (create with items, get by id, list by merchant with filters/pagination for the dashboard, update status — always through the state machine, never a raw field set).
- `orders/api/router.py`: `GET /api/v1/orders` (list, filterable by `fulfillment_status`), `GET /api/v1/orders/{id}`, `PATCH /api/v1/orders/{id}/fulfillment-status` (staff-driven transition — publishes the domain event on success). No order-creation endpoint here; orders are only created by Phase 5 (payment) / Phase 6 (COD via ordering flow) — for testing this phase in isolation, seed orders directly in a test fixture, not through an API.
- Migration: `orders`, `order_items`, `order_status_events`.
- Tests: full transition-table unit tests (no DB); repository test that `update status` rejects an illegal transition at the DB layer too (defense in depth); endpoint test for list/detail/status-update including the tenant-isolation check.

**Frontend**
- `features/orders/`: `useOrders.ts` (list, with `refetchInterval` per `TECH_STACK.md`'s cache-and-revalidate pattern — this is the concrete implementation of "order visible within seconds"), `useOrder.ts` (detail), `useUpdateOrderStatus.ts` (mutation).
- `OrdersPage.tsx`: replace placeholder with a list (status-grouped or filterable — New/Preparing/Ready/Completed), each row linking to a detail view showing items/customer/total and a status-advance button (disabled for illegal next-states, computed client-side from the same transition table shape — mirror `orders/domain/state_machine.py`'s table in `features/orders/statusTransitions.ts` so the UI can't offer an illegal move, with the server as the actual authority).
- Test: status button only shows legal next transitions for a given order state; optimistic update reconciles against server response (per `TECH_STACK.md`'s optimistic-UI note) — at minimum, test that a failed mutation rolls the UI back.

**Definition of done**: seed a `paid`/`new` order directly in the DB, see it appear in the dashboard within one poll interval, advance it New → Preparing → Ready → Completed from the UI, illegal transitions are impossible to trigger from either layer.

---

## Phase 5 — Payments (Razorpay)

Wires real money into the state machine built in Phase 4.

**Backend**
- `payments/domain/models.py`: `PaymentEvent`.
- `payments/domain/gateway.py`: `PaymentGateway` protocol (`create_link(order) -> PaymentLink`, `verify_webhook(payload, signature) -> PaymentEvent`) — the port `ARCHITECTURE.md` §4 calls for; this is what makes swapping providers later an adapter change.
- `payments/adapters/razorpay_gateway.py`: concrete `RazorpayGateway` implementing the protocol via the `razorpay` SDK.
- `payments/adapters/repository.py`: `PaymentEventRepository`, append-only, dedup on `provider_payment_id`.
- `payments/api/router.py`: `POST /api/v1/payments/webhook/razorpay` — verify signature, write `PaymentEvent`, call `orders` domain's `transition(order, "paid")`, publish `OrderPaid`. Also add `POST /api/v1/orders/{id}/payment-link` (dashboard-callable for now, since the real caller is Phase 6's checkout flow, not yet built) that creates the `Order` in `awaiting_payment` and calls `PaymentGateway.create_link`.
- `notifications` stub: for now, `OrderPaid`/`OrderConfirmedCOD` handlers just log — real WhatsApp sending is Phase 7. Wire the subscription now so Phase 7 is additive, not a rewire.
- Background job: APScheduler job (`shared/scheduler.py`, new) for the reconciliation poll (`awaiting_payment` orders past a threshold — sweep to `cancelled`) and the abandoned-order timeout sweep from §7a. Needs the timeout duration decided — flagged as an open question in `ARCHITECTURE.md` §11; pick a default (e.g. 30 min) and make it a `Settings` field so it's a one-line change later.
- Tests: webhook signature verification (valid/invalid), idempotent replay (`webhook_received_duplicate` no-ops), full order-creation → payment-link → simulated webhook → `paid` transition → event published, integration-style.

**Frontend**
- No new pages required for MVP (payment happens in WhatsApp per the brief) — but add a manual "Create test order + payment link" action gated behind a dev-only flag if useful for QA, or skip entirely and rely on backend tests + Phase 6's real flow. Recommend skipping unless you want a way to demo payments before WhatsApp is wired.

**Definition of done**: call the payment-link endpoint, simulate a Razorpay webhook against the local server (Razorpay's test-mode webhook payloads, signed with the test secret), see the order flip to `paid`/`new` and show up on the dashboard.

---

## Phase 6 — WhatsApp: Conversation Handler + Ordering Flow UI

The highest-external-dependency phase — get a WhatsApp Business test number and Meta app credentials before starting.

**Backend**
- `shared/whatsapp_client.py` (or under `conversation/adapters/`): thin `httpx`-based Graph API client (send message, send template) — the `NotificationChannel`/`OrderingSurface` port implementations live on top of this.
- `conversation/adapters/repository.py`: nothing new (delegates to `identity`/`customers`/`catalog`/`orders` services) — Conversation Handler is orchestration, not its own persistence, per `ARCHITECTURE.md` §3.
- `conversation/domain/handler.py`: resolve tenant from `phone_number_id` (needs `WhatsAppBusinessAccount` table — add a minimal version now even though full onboarding is Phase 8: just enough columns to map `phone_number_id → merchant_id`, and hand-seed one row for your test merchant), dedupe by WhatsApp message ID, greeting + intent routing (place order / track / talk to restaurant).
- `conversation/api/router.py`: `GET /api/v1/whatsapp/webhook` (Meta's verification handshake), `POST /api/v1/whatsapp/webhook` (inbound messages).
- `ordering_flow/domain/`: cart-building, order-type/payment-method selection logic — calls `catalog`, `customers`, `orders`, `payments` services (never their internals directly, per §3's ownership table).
- `ordering_flow/api/router.py`: WhatsApp Flow data-exchange endpoint (`POST /api/v1/ordering-flow/data-exchange`) implementing Meta's encrypted-payload protocol for the multi-screen in-chat cart/checkout — this is the most fiddly single piece of the whole plan; budget real time for it, and confirm during this phase (per `TECH_STACK.md` §6) whether your chosen BSP actually supports Flows well before committing further, falling back to a webview link (reusing the Vite frontend) if not.
- Tests: intent routing unit tests with mocked inbound payloads; webhook signature verification; Flow data-exchange payload encrypt/decrypt round trip against Meta's documented test vectors; end-to-end (mocked WhatsApp API) walk of §6's happy-path sequence for both online and COD.

**Frontend**
- None for the customer side (WhatsApp renders the Flow natively, per `TECH_STACK.md`) unless the Flows spike above says fall back to webview — in that case, a minimal `features/ordering/` webview flow reusing the existing React/Vite/Tailwind/shadcn stack.
- Dashboard: orders created via WhatsApp now show up on the existing Orders page (Phase 4) with no frontend changes needed — good integration checkpoint.

**Definition of done**: message the test WhatsApp number, get the greeting, place an order (online or COD) through the Flow, see the order land in the dashboard within seconds, matching the brief's success criteria.

---

## Phase 7 — Notifications

**Backend**
- `notifications/domain/channel.py`: `NotificationChannel` protocol.
- `notifications/adapters/whatsapp_channel.py`: implementation using the `shared/whatsapp_client.py` from Phase 6, sending approved template messages where required (outside the 24h customer-initiated window — verify template-message policy against your BSP, flagged in `ARCHITECTURE.md` §8).
- Wire real handlers onto the `orders/domain/events.py` bus (replacing Phase 5's log-only stubs): `OrderConfirmed`-class → "Order confirmed!"; `ready` transition (minimum, per brief) → status update message.
- Tests: event → outbound-call assertion (mock the WhatsApp client), template-vs-freeform selection logic if the 24h window matters for your BSP.

**Frontend**
- None — this phase is backend-only (outbound WhatsApp, not dashboard UI).

**Definition of done**: advancing an order to `ready` in the dashboard (Phase 4's UI) results in the test customer receiving a WhatsApp message — closes the loop the brief's success criteria describe end to end.

---

## Phase 8 — Merchant onboarding

Deferred this late deliberately: Phases 1–7 hand-seed the one or two things onboarding would otherwise gate (a `live` merchant, a `WhatsAppBusinessAccount` row), so the product is demoable well before onboarding UX exists. Build this once the core loop works, not before.

**Backend**
- `onboarding/domain/state_machine.py`: the six-state machine from `ARCHITECTURE.md` §5, same "explicit transition table" pattern as Phase 4.
- `onboarding/adapters/`: Meta embedded-signup/token-exchange client, writes to `WhatsAppBusinessAccount` (encrypt the access token via `shared/encryption.py` — this is why that module exists in the scaffold already).
- `onboarding/api/router.py`: one endpoint per step (`meta-connect`, `verify-number`, `kitchen-details`), each advancing `Merchant.onboarding_status` on success; `conversation/domain/handler.py` gets a guard added here — reject inbound chats for merchants not yet `live`.
- Migration: `whatsapp_business_accounts`; add real default (`"registered"`) to `Merchant.onboarding_status` instead of Phase 1's `"live"` placeholder.
- Tests: full state-machine transition table; step-skipping is rejected; encrypted token never appears in a log or API response.

**Frontend**
- `features/onboarding/`: replace the placeholder page with the wizard/stepper (per `TECH_STACK.md`'s pattern), driven by `Merchant.onboarding_status` as the single source of truth (a `useOnboardingStatus` query, not the existing `onboardingWizardStore.ts` Zustand store — that store stays scoped to "which step is currently displayed," per its own comment).
- Test: wizard resumes at the correct step given a mocked `onboarding_status` response.

**Definition of done**: a brand-new merchant can register, connect a WhatsApp test number, fill in kitchen details, add one menu item, and land on `live` — at which point Phase 6's Conversation Handler starts accepting their chats.

---

## Explicitly not in this plan

Everything `ARCHITECTURE.md` §11 and `TECH_STACK.md`'s "explicitly deferred" section already call out: hosting/CI/CD/observability, Phase 2 POS sync, multi-outlet, multi-user roles, delivery logistics beyond address capture. Don't build ahead of these phases.

## Suggested execution order

Phases 1–4 are pure CRUD-and-state-machine work and can move fast — they're also where the tenant-isolation and state-machine correctness bugs are cheapest to catch. Phase 5 and 6 are where external-integration risk lives (Razorpay test mode is low-friction; Meta's Flow data-exchange protocol is not) — get real sandbox credentials for both before starting Phase 5, not when you reach Phase 6. Phases 7–8 are comparatively mechanical once 1–6 exist.
