# 50 — Payment gateway dummy webhook secret placeholder + order-flow audit remediation plan

Trello card: https://trello.com/c/cA127goZ/50-follow-up-to-48-payment-gateway-dummy-webhook-secret-placeholder-order-flow-audit-remediation-plan
Branch: `claude/order-flow-audit-0ybduw`

**Deviation from the naming convention, flagged up front:** this branch does not follow the
`feature/50-...` convention `plans/README.md` describes, for the same reason documented in
`plans/48-security-audit-jwt-webhook-fixes/PLAN.md`: the session was pre-assigned to develop
on `claude/order-flow-audit-0ybduw` by the environment/orchestration layer, and that branch
already carries this session's audit work. Trello card and plan folder use ticket `50`
consistently; only the branch's literal name is off-convention.

## Problem / goal

Card #48 (merged, PR #28) fixed 3 of 4 launch-blocking security findings from the original
audit and explicitly deferred the 4th: `DummyPaymentGateway`'s webhook-verification secret
(`payments/adapters/gateway_selector.py`) is deterministically derived from the public
`merchant_id` — which is embedded in every customer-facing ordering link the bot sends.
Anyone who has received a merchant's ordering link can compute
`HMAC-SHA256(body, f"dummy-secret-{merchant_id}")` and forge a `payment.captured` webhook,
getting a free order before that merchant configures real Razorpay keys in Settings.

A second, broader audit (this session, 4 parallel sub-agents: order-flow correctness/
concurrency, architecture/design patterns, API security/multi-tenancy, frontend/testing/
observability/DevOps) surfaced ~40 further findings. The user's explicit instruction for
this card: fix the payment-gateway issue now, but only with **placeholders** — real
Razorpay keys will be supplied later via env vars the user fills in directly — and turn the
remaining findings into a **plan**, not code, for now.

## Scope

**Implement now:**
- `backend/src/shared/config.py` — add `payments_dummy_gateway_secret` (new setting,
  `Field(default_factory=lambda: secrets.token_urlsafe(32))` so it's a random, unguessable
  value if the env var is left unset); remove the hardcoded literal default on
  `platform_razorpay_webhook_secret`, same `default_factory` treatment.
- `backend/src/payments/adapters/gateway_selector.py` — `resolve_credentials()` reads the
  new setting instead of deriving from `merchant_id`.
- `backend/.env.example` — document both as placeholders: leave unset for now (a random
  value is generated at process startup), set explicitly only if dummy-webhook signatures
  need to survive restarts/multiple workers, and swap to real values when available
  (per-merchant real Razorpay credentials still go through the dashboard Settings page —
  unrelated to this env var; the platform billing secret comes from Razorpay's dashboard
  once `PLATFORM_RAZORPAY_KEY_ID`/`_SECRET` are configured for production).
- Run backend test suite + ruff + mypy; add/adjust any test asserting the old
  `dummy-secret-{merchant_id}` string if one exists.

**Explicitly NOT changed:** per-merchant real Razorpay credential storage (stays DB +
dashboard Settings UI, correct existing multi-tenant design) — this only touches the
*dummy/placeholder fallback* path used before a merchant configures real keys.

**Planning only (this card writes the backlog; implementation is future cards):** all
remaining findings below, prioritized P0-P3.

## Remaining findings — prioritized backlog

### P0 — correctness/security, fix next
1. **Razorpay webhook idempotency race** — `payments/api/router.py:42-54`, non-unique index
   on `payment_events.provider_payment_id`. Concurrent redelivery can double-process a
   payment (duplicate "order confirmed" messages, duplicate success rows). Fix: unique
   (partial) constraint + `INSERT ... ON CONFLICT` or `SELECT ... FOR UPDATE` on the order
   row before transitioning.
2. **Checkout transaction ordering** — `ordering_flow/domain/checkout.py:203-214` calls the
   real Razorpay API between an uncommitted order flush and the final commit; a post-gateway
   commit failure leaves a live payment link pointing at a rolled-back order. Fix: commit
   the order as `awaiting_payment` first, then call the gateway and persist the link in a
   second commit (or add compensating cancellation on gateway-call failure).
3. **No availability re-check at checkout** — `ordering_flow/domain/checkout.py:127-135`
   only checks item existence, not `is_available`, so a customer can order an item the
   merchant just marked sold out. Fix: re-check `is_available` in the item-resolution loop.
4. **No CI at all** — no `.github/` directory; lint/typecheck/test/build scripts exist but
   nothing gates merges. Fix: GitHub Actions workflow running backend
   (`ruff check`, `mypy src`, `pytest`) and frontend (`lint`, `typecheck`, `test`, `build`)
   on every PR, plus a dependency-audit/secret-scan step.

### P1 — correctness/architecture, fix soon
5. **No row locking on state transitions** — `orders/adapters/repository.py:192-227`, no
   `SELECT ... FOR UPDATE`/version column anywhere. Two concurrent fulfillment/payment
   writes (staff PATCH vs. staff PATCH, or vs. the webhook) can both pass validation against
   stale state and both commit, double-firing customer notifications.
6. **Bidirectional orders↔payments coupling** — `payments/api/router.py:66-92` directly
   mutates `Order`/`Appointment` state from the API layer instead of delegating to a
   domain/service function; `orders/api/router.py` reaches into `payments/adapters`
   directly the other way. Contradicts the documented "Payment emits, Order reacts"
   architecture (`ARCHITECTURE.md` §3/§9a). Fix: route through one boundary — an
   orders-owned "record payment result" use case, or make it properly event-driven.
7. **Customer find-or-create race** — `customers/adapters/repository.py:65-91` does
   SELECT-then-INSERT despite a real unique DB constraint on
   `(merchant_id, whatsapp_number)`; concurrent first-contact webhooks can raise an
   unhandled `IntegrityError` (500). Fix: `pg_insert(...).on_conflict_do_nothing()` +
   re-select, matching the pattern already used for `MessageDedupeRepository`.
8. **Missing DB indexes** — no index on `orders.fulfillment_status`/`payment_status`/
   `placed_at` (every dashboard list/summary sequential-scans); no unique/index on
   `whatsapp_business_accounts.phone_number_id` (the hottest read path — resolved on every
   inbound WhatsApp message); `payment_events.provider_payment_id` index is non-unique.
9. **No structured logging / correlation IDs** — `shared/logging.py` is plain
   `logging.basicConfig`; zero logging calls in `orders/api/router.py` or
   `payments/api/router.py`. A payment or fulfillment change can't be traced to a specific
   order from logs. Fix: structured (JSON) logging + a request/order correlation ID
   threaded through the webhook → domain → notification path.

### P2 — hardening, fix when capacity allows
10. **Customer PII stored in plaintext** — `whatsapp_number`, address fields are plain
    columns; the existing Fernet helper is only used for API credentials. Fix: column-level
    encryption on PII, matching the credentials pattern.
11. **No rate limiting anywhere** — `/auth/login`, `/auth/register`, public checkout, and
    webhook endpoints are all open to brute-force/flood.
12. **No refresh-token revocation** — `identity/domain/auth.py:98-103` never invalidates a
    rotated/logged-out refresh token; it stays valid up to 30 days regardless. Fix: track
    issued/rotated `jti`s server-side, invalidate on logout/rotation.
13. **No pagination on list endpoints** — `orders`, `customers`, `catalog` list endpoints
    return the full unbounded result set per tenant.
14. **Abandoned-order sweep skips the audit trail** — `shared/scheduler.py:42-58` calls the
    raw domain transition function directly, bypassing `OrderRepository`'s wrapper, so
    auto-cancellation never gets an `OrderStatusEvent` row (unlike every manual transition).

### P3 — maintainability & extensibility polish
15. **`conversation/domain/handler.py` god file** — 770 lines, imports from 12 other
    modules directly, `_reply_for_intent` alone ~200 lines of nested branching. Split into
    per-intent handler modules under `conversation/domain/intent_handlers/`.
16. **Duplicated event-bus infrastructure** — `orders/domain/events.py` and
    `appointments/domain/events.py` are a byte-for-byte-identical pub-sub engine with only
    event types differing. Extract a generic `EventBus[T]` into `shared/`.
17. **Magic strings for status** — `PaymentStatus`/`FulfillmentStatus` are plain `str`
    aliases; nothing but the frozensets stops a typo'd status literal from compiling. Use
    `StrEnum` for both status families (mypy would then catch a typo at type-check time).
18. **Frontend/backend transition-table drift risk** — `statusTransitions.ts` hand-copies
    the backend's transition table with a "mirrors backend exactly" comment but no shared
    source of truth. Generate it from the backend contract instead.
19. **Hand-rolled public tenant resolution** — `ordering_flow/api/router.py` reimplements
    tenant resolution via a local helper 3x instead of a `PublicTenant` FastAPI dependency
    mirroring `CurrentTenant`.
20. **A11y gaps** — missing `aria-label` on ordering-page qty +/- buttons; `OrderDetailPage`/
    `OrdersPage` only branch on `isLoading`, not `isError` (a fetch error renders as "not
    found"/empty instead of an error state); invalid `aria-expanded` on a bare `<tr>` in
    `OrdersPage` (redundantly mitigated by an adjacent labeled button, but still invalid
    markup).
21. **Doc drift** — `CLAUDE.md`'s "Order flow" section claims `cod_collected` is unreachable
    and that there's no address update/delete API; both are now false
    (`orders/api/router.py:167-194`'s `/collect-cod-payment`,
    `customers/api/router.py:80-110`'s `PATCH`/`DELETE .../addresses/{id}`). Update the doc.

Each backlog item above is also tracked as a Trello checklist item on card #50 under
"Backlog — planned, not implemented", to be split into its own card (with its own
`plans/<ID>-slug/` folder) when picked up.

## Files to touch (this card only)

- `backend/src/shared/config.py`
- `backend/src/payments/adapters/gateway_selector.py`
- `backend/.env.example`

## Risks

- Low: the new `payments_dummy_gateway_secret`/`platform_razorpay_webhook_secret` defaults
  are random-per-process (via `default_factory`) rather than fixed. In a multi-worker
  deployment without the env var set, dummy-mode webhook signatures signed by one worker
  process would not verify against another worker's independently-generated secret. This
  only affects the *dummy/test* gateway path (pre-real-keys); acceptable for now per the
  user's "placeholder" instruction, and the mitigation (set the env var to a fixed value)
  is exactly what the placeholder is for.

## Acceptance criteria

- [x] Dummy webhook secret no longer derivable from merchant_id/public data.
- [x] Platform billing webhook secret no longer hardcoded in source.
- [x] `.env.example` documents both as placeholders.
- [x] Backend tests green.
- [x] This PLAN.md has the full prioritized backlog for remaining findings.

## Progress Log

**2026-09-07 (later)** — Every item in the P0-P3 backlog above has now been picked up
and closed out across cards #51 (P0) and #52 (P1-P3), except the three items explicitly
flagged as skipped in card #52 (god-file split, repo-wide StrEnum conversion, frontend/
backend transition-table codegen) — see `plans/51-p0-order-flow-correctness-ci/PLAN.md`
and `plans/52-batch-remediation-p1-p3/PLAN.md` for the full record and final
consolidated test results (853/853 backend, full frontend suite green).

**2026-09-07** — Implemented the placeholder fix (commit `a1cd862`). Replaced the
merchant_id-derived dummy webhook secret and the hardcoded platform billing webhook secret
literal with `Field(default_factory=lambda: secrets.token_urlsafe(32))` settings, sourced
from new/existing env vars (`PAYMENTS_DUMMY_GATEWAY_SECRET`,
`PLATFORM_RAZORPAY_WEBHOOK_SECRET`) the user will set later. Updated the 6 test call sites
that hardcoded the old `dummy-secret-{merchant_id}` string to read
`get_settings().payments_dummy_gateway_secret` instead, added a regression test asserting
the secret is not derivable from merchant_id, and pinned both new settings to deterministic
test-only values in `conftest.py` (matching the existing JWT_SECRET/WHATSAPP_WEBHOOK_VERIFY_TOKEN
convention). Full backend suite: 832/832 passing; `ruff check` clean; `mypy src` clean
except the one pre-existing `payments/api/router.py:62` finding already documented in card
#48/`IMPLEMENTATION_PLAN.md` as unrelated/predating this work. Wrote the full P0-P3 backlog
above and mirrored it onto Trello card #50's "Backlog" checklist. Pushed to
`claude/order-flow-audit-0ybduw`. No deviations from the plan.
