# 51 — P0 order-flow correctness: webhook idempotency, checkout ordering, stock re-check, CI

Trello card: https://trello.com/c/hFGrMQei/51-p0-order-flow-correctness-webhook-idempotency-race-checkout-commit-ordering-stock-re-check-ci
Branch: `claude/order-flow-audit-0ybduw` (pre-assigned to this session, same documented
deviation from `feature/51-...` as cards #48/#50 — see those plans for the reasoning).

## Problem / goal

P0 tier of card #50's remediation backlog. Four items, not implemented yet — this plan is
implementation-ready but **no code has been touched for this card**. Written up before
starting per the mandatory workflow, and to get a go-ahead before touching payment-webhook
correctness code and a DB migration.

## 1. Webhook idempotency race

**Root cause:** `payments/api/router.py`'s `razorpay_webhook`/`razorpay_appointment_webhook`
fetch the `Order`/`Appointment` with a plain `SELECT` (`OrderRepository.get()`,
`AppointmentRepository.get()`), then mutate in Python, then commit. Two concurrent
deliveries of the same webhook (Razorpay's documented retry behavior) can both pass the
`already_processed` check (itself an unprotected `SELECT` on `provider_payment_id`) before
either commits, both read the order in its pre-transition state, both pass
`transition_payment_status`'s validation, and both commit — duplicate `payment_succeeded`
events, duplicate `OrderPaid` publishes, duplicate "order confirmed" WhatsApp messages.

**Fix — row lock at the point of transition:**
1. Add `OrderRepository.get_for_update(tenant, order_id)` — identical to `get()` but with
   `.with_for_update()` on the select. Same for `AppointmentRepository`.
2. In `razorpay_webhook`, replace the `OrderRepository(session).get(...)` call (line 62)
   with `get_for_update(...)`. Same for `razorpay_appointment_webhook`'s
   `AppointmentRepository(session).get(...)` call (line 146).
3. **Also route both wrapper methods `OrderRepository.transition_fulfillment_status` and
   `transition_payment_status` (lines 179-229) through `get_for_update()` instead of
   `get()`.** These are the funnel every *other* order-state write goes through (the
   dashboard's manual fulfillment PATCH, the COD-collected endpoint) — locking here closes
   backlog item P1-#5 (concurrent staff-PATCH race) as a side effect of this same change,
   at effectively zero extra cost since the method already exists and is already the
   "defense in depth" funnel per its own docstring.

   Why the lock actually fixes the race: request B blocks on the `SELECT ... FOR UPDATE`
   until request A's transaction commits and releases the row lock. B then re-reads the
   *post-A* state (`payment_status` already `paid`), and `transition_payment_status`
   correctly raises `IllegalTransitionError` (paid → paid isn't legal) — which the webhook
   handler already treats as "duplicate" (existing `except IllegalTransitionError` branch,
   lines 69-80). No new error-handling branch needed, just the lock.

4. **Defense-in-depth migration:** add a partial unique index —
   `CREATE UNIQUE INDEX ix_payment_events_provider_payment_id_unique ON payment_events
   (provider_payment_id) WHERE provider_payment_id IS NOT NULL` (replacing the existing
   non-unique index from migration `60d2ca6b9bf0`). Not required for correctness once the
   row lock is in place (the lock serializes before any insert happens), but cheap and
   catches a future regression loudly (a raised `IntegrityError`) instead of silently.
   No `ON CONFLICT` handling added around `PaymentEventRepository.create()` — with the row
   lock in place a conflict here genuinely can't happen in the webhook path, and the
   project's own convention (CLAUDE.md) is not to add error handling for scenarios that
   can't happen.

**Files:** `orders/adapters/repository.py`, `appointments/adapters/repository.py`,
`payments/api/router.py`, a new Alembic migration.

**Test:** two concurrent `POST /api/v1/payments/webhook/razorpay/{merchant_id}` requests
with identical signed payloads (via `asyncio.gather`) → assert exactly one
`payment_succeeded` `PaymentEvent`, one `webhook_received_duplicate` event, and the order
lands on `paid` (not double-transitioned/errored).

## 2. Checkout transaction ordering

**Root cause:** `ordering_flow/domain/checkout.py`'s online-payment branch (lines 188-214)
flushes (not commits) the order, then calls `gateway.create_link()` — a real external
Razorpay API call for real merchants — and only commits afterward. If the process dies or
the DB connection drops between the gateway call succeeding and `session.commit()`
completing, a live Razorpay payment link now points at an `order_id` that was never
durably persisted (rolled back on session teardown). A customer paying into that link's
money is captured with no matching order.

**Fix:** split into two transactions.
1. Create the order (`payment_status="awaiting_payment"`) and commit immediately —
   `await order_repo.create(...)` then `await session.commit()` — *before* calling the
   gateway.
2. Call `gateway.create_link(...)`.
3. If the gateway call raises, the order already exists in `awaiting_payment` with no
   link — a safe, recoverable state (visible in the dashboard, customer can be re-sent a
   link or the order can be cancelled by the abandoned-order sweep). Let the exception
   propagate; `perform_checkout`'s caller (the API router) already returns a 5xx today for
   an unhandled exception, which is correct — no new handling needed.
4. On success, write the `link_created` `PaymentEvent` and commit in a second transaction.

**Residual risk, accepted:** if the *second* commit fails after a successful gateway call,
the order exists (good — no phantom payment) but the `PaymentEvent` linking
`provider_order_id → order_id` is missing, so the webhook's `get_latest_by_provider_order_id`
lookup 404s until manually reconciled. This is a much smaller, more recoverable failure
mode than the current one (order not existing at all) and is called out explicitly rather
than solved with a retry loop — retrying a `commit()` after an unknown-cause failure risks
double-writing the event; out of scope for this pass.

**Files:** `ordering_flow/domain/checkout.py`.

**Test:** mock the gateway to raise after order creation, assert the order still exists in
`awaiting_payment` (not rolled back) and the endpoint surfaces a 5xx rather than silently
losing the order.

## 3. No availability re-check at checkout

**Root cause:** `perform_checkout`'s item-resolution loop (lines 124-137) calls
`item_repo.get(tenant, line.item_id)`, which checks tenant ownership but not
`is_available`. Only the public catalog *listing* endpoint filters unavailable items
(`ItemRepository.list(..., include_unavailable=False)`), so a customer whose ordering page
was already open when the merchant marked an item sold out can still complete checkout for
it.

**Fix:** in the same loop, after the `None` check, raise a new
`ItemUnavailableError(item_id)` (mirroring `ItemNotFoundError`'s shape) if
`not item.is_available`. Wire it in the API layer(s) that call `perform_checkout`
(`ordering_flow/api/router.py`, `payments/api/dashboard_router.py`'s `/test-checkout`) to a
409, next to the existing `ItemNotFoundError → 404` handling.

**Files:** `ordering_flow/domain/checkout.py`, `ordering_flow/api/router.py`,
`payments/api/dashboard_router.py`, matching call sites in `appointments/api/router.py` if
it shares this path (verify during implementation).

**Test:** mark an item unavailable, attempt checkout with it, assert 409 and no `Order`
row created.

## 4. CI

**Fix:** `.github/workflows/ci.yml` with two jobs:
- **backend:** `postgres:16` service container: `uv sync`, `alembic upgrade head` against
  it, `uv run ruff check .`, `uv run mypy src`, `uv run pytest`. Needs `DATABASE_URL`/
  `TEST_DATABASE_URL` env pointing at the service container, matching `conftest.py`'s
  existing `TEST_DATABASE_URL` fallback.
- **frontend:** `npm ci`, `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`.

Both on `pull_request` and `push` to `main`.

**Also, found while validating card #50's test run (had to `export
SECRETS_ENCRYPTION_KEY=...` by hand to get 3 tests green):** `conftest.py` pins
deterministic test-only values for `JWT_SECRET`/`WHATSAPP_WEBHOOK_VERIFY_TOKEN`/
`META_APP_SECRET`/`PAYMENTS_DUMMY_GATEWAY_SECRET`/`PLATFORM_RAZORPAY_WEBHOOK_SECRET` via
`os.environ.setdefault`, but not `SECRETS_ENCRYPTION_KEY` — so any test touching
`shared/encryption.py` fails in a clean environment (CI included) unless the runner sets
it externally. Fix: add the same `setdefault` pattern for a fixed test-only Fernet key,
removing the need for CI (or a fresh clone) to generate/export one.

**Files:** `.github/workflows/ci.yml` (new), `backend/tests/conftest.py`.

## Risks

- Row locking (`FOR UPDATE`) inside `transition_fulfillment_status`/`transition_payment_status`
  changes concurrency behavior for every existing caller of those methods, not just the
  webhook — a second concurrent call on the same order now blocks (briefly) instead of
  racing. This is the intended fix, not a side effect to work around, but flagging since
  it's a behavior change beyond the webhook path specifically named in P0.
- The checkout-ordering split (item 2) changes when the order becomes visible in the
  dashboard (immediately on creation, before the payment link exists, rather than only
  after both are ready) — cosmetic, not a correctness risk, but worth knowing if the
  dashboard's order list doesn't handle a link-less `awaiting_payment` order gracefully
  today (verify during implementation).
- CI's Postgres-service-container setup is new infra for this repo; first run may need
  iteration on service health-check timing.

## Files to touch

- `backend/src/orders/adapters/repository.py`
- `backend/src/appointments/adapters/repository.py`
- `backend/src/payments/api/router.py`
- `backend/src/ordering_flow/domain/checkout.py`
- `backend/src/ordering_flow/api/router.py`
- `backend/src/payments/api/dashboard_router.py`
- `backend/src/appointments/api/router.py` (verify)
- `backend/alembic/versions/` (new migration)
- `backend/tests/conftest.py`
- `.github/workflows/ci.yml` (new)
- New/updated tests across the above

## Acceptance criteria

- [ ] Concurrent redelivery of the same webhook cannot double-transition an order.
- [ ] Gateway-call/commit failure never leaves a payment link pointing at a nonexistent
      order.
- [ ] Checkout rejects an unavailable item with a 409, no order created.
- [ ] CI runs lint/typecheck/test/build on every PR for backend + frontend, green.
- [ ] Full backend + frontend suites green; ruff/mypy/biome clean.

## Progress Log

**2026-09-07** — Plan written, Trello card #51 created, not yet implemented. Awaiting
go-ahead before touching payment-webhook code and adding a migration.

**2026-09-07** — Item 1 (webhook idempotency race) implemented, one at a time per user
request. `OrderRepository.get_for_update()`/`AppointmentRepository.get_for_update()` added
(SELECT ... FOR UPDATE); used in both webhook handlers and inside
`transition_fulfillment_status`/`transition_payment_status` (closing P1-#5 for free, as
planned). Migration `fcd1cd201c55` adds the partial unique index on
`payment_events.provider_payment_id`.

Deviation from the plan, caught during testing: the plan's index was `WHERE
provider_payment_id IS NOT NULL` with no `event_type` filter. That broke the *existing*,
intentional design — both webhook handlers write a `webhook_received_duplicate`
`PaymentEvent` row reusing the same `provider_payment_id` on every redelivery, as an audit
trail (confirmed by `test_webhook_redelivery_is_idempotent` failing against the new index).
Fixed by scoping the unique index to `event_type IN ('payment_succeeded',
'payment_failed')` -- the real invariant is "at most one *processing* event per payment
id", not "at most one row total". Migration regenerated (old `c3af89a03a8b` file deleted
before it was committed/pushed anywhere, so no orphaned migration in history).

Added `test_concurrent_webhook_redelivery_does_not_double_process` (genuine
`asyncio.gather` concurrency, not sequential) — passed 5/5 repeated runs. Full backend
suite: 833/833 passing (was 832 before this item); ruff clean; mypy clean aside from the
one pre-existing `payments/api/router.py` finding (now at a shifted line number, same
underlying pre-existing type looseness, not a new issue -- verified by comparing against
the finding already documented from card #48/#50).
