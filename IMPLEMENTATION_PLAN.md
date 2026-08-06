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

## Phase 5 — Payments (Razorpay) ✅ done

Wires real money into the state machine built in Phase 4. Built without real Razorpay credentials (none were available) — see the "Per-merchant credentials & Settings page" addition below for how that's handled, and why it doesn't need revisiting when real keys arrive.

**Deviations from the original plan, and why:**
- **Razorpay credentials are per-merchant, not global `Settings` fields.** Each merchant's payment link should settle into *their* Razorpay account, not a shared platform one — this is the realistic model for independent restaurants. `payments/domain/models.py`'s `MerchantPaymentCredentials` (1:1 with `Merchant`) holds `razorpay_key_id` (clear text — it's sent to the browser in real Checkout flows anyway) and `razorpay_key_secret_encrypted` (Fernet, via `shared/encryption.py`). `PUT /api/v1/payments/settings` lets a merchant set/update these from the dashboard.
- **`PaymentGateway` has two adapters, not one.** `payments/adapters/razorpay_gateway.py` (real SDK) and `payments/adapters/dummy_gateway.py` (fabricates a local checkout URL instead of calling Razorpay's API). `payments/adapters/gateway_selector.py`'s `get_payment_gateway(key_id, key_secret)` picks by inspecting the key_id prefix (`rzp_test_`/`rzp_live_` → real, anything else → dummy) — so entering real test-mode keys in Settings is the only thing that flips a merchant over to the real gateway, no code change or redeploy. Critically, `verify_webhook` on *both* adapters does the exact same HMAC-SHA256(body, secret) Razorpay's real webhooks use, so signature-verification logic is fully exercised now regardless of whether the secret on file is real or a placeholder.
- **The WhatsApp side of the same idea was pulled forward from Phase 8.** `onboarding/domain/models.py`'s `WhatsAppBusinessAccount` (per `ARCHITECTURE.md` §1, built now rather than waiting for the full onboarding wizard) holds per-merchant `phone_number_id` + `access_token_encrypted`, settable via `PUT /api/v1/onboarding/whatsapp`. No Meta OAuth handshake yet (that's still Phase 8) — the merchant pastes these values directly, which is in fact a legitimate WhatsApp Cloud API connection method, not just a stand-in.
- **A dashboard-only `POST /api/v1/payments/test-checkout` endpoint stands in for order creation**, since Phase 6 (the real WhatsApp ordering flow) doesn't exist yet and Phase 4 deliberately shipped no order-creation endpoint. It identifies the customer by phone number via `find_or_create` (the same call Phase 6 will make), not a pre-existing `customer_id` — no UI exists to create a customer otherwise. Superseded by Phase 6, not extended by it.
- Reconciliation-against-the-provider (polling Razorpay's payment-status API for stuck orders) was **not** built — there's nothing real to poll against without live credentials. The abandoned-order timeout sweep *was* built (`shared/scheduler.py`, APScheduler, `Settings.abandoned_order_timeout_minutes`, default 30) since it's self-contained (a DB query based on elapsed time, no external call).

**Frontend**: added a Settings page (`features/settings/`) — Razorpay and WhatsApp credential forms side by side, each showing a Live/Test-mode or connection-status badge, per the plan's UI ask. Also added `features/orders/CreateTestOrderForm.tsx` (collapsible, on the Orders page) to exercise `test-checkout` from the dashboard.

**Definition of done** (met): create a test order from the dashboard with a dummy Razorpay key on file, get a fake payment link back, simulate a Razorpay-shaped webhook signed with the same dummy secret, watch the order flip to `paid`/`new` and advance through the full kitchen workflow — verified with a live browser walk, not just backend tests.

---

## Phase 6 — WhatsApp: Conversation Handler + Ordering Flow UI ✅ done

The highest-external-dependency phase. No WhatsApp Business test number or Meta app credentials were available (same situation as Phase 5's Razorpay keys), which changed the plan in one significant way — see the Flows decision below.

**Deviation: WhatsApp Flow was never attempted; went straight to the webview fallback.** The plan's own text already names this fallback ("confirm... whether your chosen BSP actually supports Flows well... falling back to a webview link if not") — but that framing assumes a live BSP connection to test against. Here there was no live Meta connection at all, not just uncertain BSP support, and Flow's encrypted data-exchange protocol requires exchanging a real public key with Meta's dashboard to mean anything — building it blind would be unverifiable code, not a tested feature. The webview is fully testable end-to-end (real HTTP, real browser rendering), so per the architecture's own decision procedure it was the responsible choice, not a corner cut. `ordering_flow/api/router.py` implements the customer-facing webview's backend (`GET /{merchant_id}/menu`, `POST /{merchant_id}/checkout`, both public/unauthenticated, scoped by `merchant_id` in the path); `frontend/src/features/ordering/OrderingPage.tsx` is the webview itself (menu, cart, checkout form), reusing the existing React/Vite/Tailwind/shadcn stack exactly as `TECH_STACK.md` §6 anticipated for this fallback.

**Backend, as built:**
- `conversation/adapters/whatsapp_client.py`: `GraphApiWhatsAppSender` (real Graph API calls) behind a `WhatsAppSender` protocol. Every send is best-effort — a failed call (no live WABA behind a merchant's dummy credentials, expired token, network error) is logged and returns `False` rather than raising, so the whole *inbound* side (tenant resolution, dedupe, intent routing, order creation) is fully exercisable without a live Meta connection; only actual outbound delivery no-ops until real credentials are on file. Verified live: a real HTTP call to `graph.facebook.com` with a dummy token failed exactly as expected and was handled gracefully, no crash, webhook still ack'd 200.
- `conversation/domain/models.py` + `adapters/repository.py`: `ProcessedWhatsAppMessage` for dedup, an atomic `INSERT ... ON CONFLICT DO NOTHING` (not a check-then-insert) so two near-simultaneous webhook redeliveries can't both pass.
- `conversation/domain/webhook_parser.py` + `intents.py`: parses Meta's webhook JSON into a clean `InboundMessage`, then classifies intent (button reply takes priority; free-text keyword matching otherwise, structured/guided per the brief, not AI parsing). Found and fixed a real bug here during testing: "track my order" matched `PLACE_ORDER`'s generic "order" keyword before `TRACK_ORDER`'s "track" keyword, since dict iteration checked the broader intent first — fixed by ordering narrower intents first.
- `conversation/domain/handler.py`: resolves tenant from `phone_number_id` (via `onboarding.adapters.repository`'s new `get_by_phone_number_id`, added to the `WhatsAppBusinessAccount` repository built in Phase 5), dedupes, finds-or-creates the `Customer`, routes by intent (place order → sends the webview link; track order → looks up the customer's most recent order via a new `OrderRepository.list_for_customer`; talk to restaurant → fixed reply; anything else → greeting/intent-menu buttons).
- `conversation/api/router.py`: `GET`/`POST /api/v1/whatsapp/webhook`. The `WhatsAppSender` is FastAPI-dependency-injected (not a module-level singleton), so tests override it with a fake instead of making real network calls.
- **Refactor**: the cart→Order(+payment-link) orchestration that lived inline in Phase 5's `payments/api/dashboard_router.py` test-checkout was extracted into `ordering_flow/domain/checkout.py`'s `perform_checkout` — now both the dashboard's test-checkout shortcut and the real customer-facing webview checkout call the same function, so they can't drift apart.
- Tests: webhook payload parsing (text/button/status-callback/multi-entry), intent classification (all keyword/button cases plus the bug above), handler tests with a fake sender (unknown number, dedup, greeting, each intent, customer creation), webhook endpoint tests (verify handshake, dependency-injected fake sender, dedup at the HTTP layer), public menu/checkout tests (availability filtering, tenant isolation, 404s).

**Frontend**: `features/ordering/OrderingPage.tsx` (public route `/order/:merchantId`, outside `RequireAuth` and the dashboard `Layout`) — menu browsing, quantity-based cart, checkout form (phone/name/payment method), confirmation screen with the payment link for online orders.

**Definition of done** (met, adapted for no live WhatsApp number): simulated an inbound "hi" webhook → got a real (logged, non-crashing) send attempt and the correct intent-menu response computed server-side; simulated a `place_order` button reply → got the correct webview link computed; opened that exact link in a real browser → browsed the menu → checked out online → got a payment link; simulated a signed Razorpay webhook against it → order flipped to `paid`/`new` and appeared on the merchant dashboard within seconds; advanced its fulfillment status — the full loop the brief describes, started from a WhatsApp-shaped webhook rather than a live WhatsApp message, but the entire path in between is real, tested code, not a stub.

---

## Phase 7 — Notifications ✅ done

Wires real handlers onto the `orders/domain/events.py` bus built in Phase 4, replacing what had been a no-subscriber (silent) bus. Built without a live WhatsApp connection (same situation as Phases 5/6) — the send attempt is real, only delivery no-ops against dummy credentials.

**Deviations from the original plan, and why:**
- **The event bus had to become async.** It was originally synchronous (`Handler = Callable[[OrderEvent], None]`); sending a WhatsApp message is an HTTP call, so `Handler` is now `Callable[[OrderEvent], Awaitable[None]]` and `publish` is `async def`, awaited in registration order. Updated all three existing publishers (`orders/api/router.py`'s fulfillment-status endpoint, `ordering_flow/domain/checkout.py`'s COD branch, `payments/api/router.py`'s Razorpay webhook handler) to `await publish(...)`.
- **No template-vs-freeform message selection was built.** The 24h customer-initiated-conversation window (`ARCHITECTURE.md` §8) matters for real WhatsApp Business API traffic, but without a live BSP connection there's no policy to verify or template ID to send against — flagged here rather than guessed at. `notifications/adapters/whatsapp_channel.py` sends plain `send_text` messages for all three notification kinds; swapping in template messages later is a one-file change (the `NotificationChannel` protocol and its call sites don't need to know).
- **One method per notification kind, not a generic `notify(message)`.** `notifications/domain/channel.py`'s `NotificationChannel` protocol has `notify_order_confirmed` / `notify_order_ready` / `notify_order_completed` — keeps the actual message copy (and, later, which ones need a template) owned by the adapter, not scattered across every call site.
- **A swappable module-level singleton, not FastAPI `Depends()`, for the channel.** Order events (and their notification side effects) aren't triggered by an HTTP request the way sending a webhook reply is — the notification handlers subscribed in `notifications/wiring.py` fire off the domain event bus, with no request/response cycle to hang a dependency override on. `wiring.py` exposes `set_notification_channel`/`get_notification_channel` instead, which tests use to swap in a fake channel around calls that would otherwise trigger a real (if gracefully-failing) network attempt.
- **`register_notification_handlers()` is called at `app.py` module level, not inside `lifespan`.** `lifespan` doesn't run under the `ASGITransport` the test `client` fixture uses, so subscriptions registered there would never actually fire in tests — unlike `shared/scheduler.py`'s APScheduler job, which correctly stays in `lifespan` since it's a genuinely runtime-only concern. Registration is idempotent (a guard flag) so importing `app` more than once — which pytest does per test module — never double-subscribes and double-sends.
- Notifications are fire-and-forget from the publishing request's point of view: a failed or slow send is logged and swallowed (`WhatsAppSender`'s existing graceful-failure contract from Phase 6), never blocks or fails the order-status-update / checkout / payment-webhook request that published the event. Verified live: advancing an order to `ready` against dummy WhatsApp credentials logged `WhatsApp send failed: 403 Forbidden` and still returned `200 OK` for the status update itself.

**Backend, as built:**
- `notifications/domain/channel.py`: `NotificationChannel` protocol.
- `notifications/adapters/whatsapp_channel.py`: `WhatsAppNotificationChannel`, built on the `WhatsAppSender` from Phase 6 — looks up the merchant's `WhatsAppBusinessAccount`, the order, and its customer in a fresh DB session (handlers run after the triggering request already committed, so there's nothing to share a transaction with), then sends.
- `notifications/wiring.py`: subscribes `OrderPaid` and `OrderConfirmedCOD` → confirmed message; `OrderReady` → ready message; `OrderCompleted` → completed message.
- Tests (`tests/test_notifications.py`): `WhatsAppNotificationChannel` against a fake sender (message content per event kind, graceful `False` on missing WABA/order/customer, sender-failure propagation); `wiring` (idempotent registration, each event type routes to the correct notification method, channel-swap isolation).

**Frontend**
- None — this phase is backend-only (outbound WhatsApp, not dashboard UI), as planned.

**Definition of done** (met, adapted for no live WhatsApp connection): advancing an order to `ready` via the dashboard triggers a real outbound send attempt to `graph.facebook.com` with the merchant's on-file (dummy) credentials — rejected by Meta as expected, logged, and non-blocking — closing the loop the brief's success criteria describe, short of an actual delivered message pending real BSP credentials.

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
