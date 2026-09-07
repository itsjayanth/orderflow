# 49 — Merchant Subscription & Billing Layer

Trello card: https://trello.com/c/7bC0aRrW/49-merchant-subscription-billing-layer
Branch: `claude/merchant-subscription-billing-fnd4oh` (assigned by the harness; per CLAUDE.md's workflow this stands in for a `feature/49-...` branch name — noted as a deviation, not a re-creation of the branch).
Status: **pre-coding write-up — awaiting user confirmation before any implementation.** Per the task prompt's own §0.4 ("Do not start coding yet"), this document is (a) the read of current code, (b) the Phase 17 write-up, (c) the data model, and (d) open questions, all in one place, plus the implementation plan the CLAUDE.md workflow requires.

---

## (a) Read of the current, actual code (verified by 3 parallel Explore subagents + direct reads, not just the docs)

### Payments module (`payments/`) — the pattern to mirror
- Hexagonal: `domain/gateway.py` (`PaymentGateway` Protocol — `create_link`, `verify_webhook`; `PaymentLink`/`VerifiedPaymentEvent` frozen dataclasses; `WebhookVerificationError`), `domain/models.py` (`MerchantPaymentCredentials`, `PaymentEvent`), `adapters/{dummy_gateway,razorpay_gateway,gateway_selector,repository}.py`, `api/{router,dashboard_router,schemas}.py`.
- Two adapters, duck-typed against the Protocol (no explicit inheritance). `DummyPaymentGateway` fabricates a local URL/ID with zero network calls but does the **real** HMAC-SHA256(body, secret) verification — same as the real adapter — so signature logic is fully exercised without real credentials.
- `gateway_selector.get_payment_gateway(key_id, key_secret)` picks Razorpay vs Dummy by `key_id` prefix (`rzp_test_`/`rzp_live_`); `resolve_credentials()` falls back to a deterministic `f"dummy-secret-{merchant_id}"` when no credentials are on file, so the HMAC check always has something to compare against.
- `MerchantPaymentCredentials`: 1:1 with `Merchant` (`merchant_id` is the PK itself, no surrogate key), `razorpay_key_id` clear-text, `razorpay_key_secret_encrypted` via `shared/encryption.py`'s Fernet (fails closed if `SECRETS_ENCRYPTION_KEY` unset).
- `PaymentEvent`: append-only, no DB unique constraint — dedupe is application-level: look up `provider_payment_id`; if found, write a `webhook_received_duplicate` audit row and return `{"status": "duplicate"}` without re-mutating. A second belt-and-suspenders layer: if the state machine rejects the transition as illegal (already settled), that's also caught and logged as `webhook_received_duplicate`, not raised. Order resolution goes through `provider_order_id` recorded at link-creation time — never a client-echoed tenant field.
- Signature header: `X-Razorpay-Signature`. Verification: `hmac.new(secret, body, sha256).hexdigest()` compared with `hmac.compare_digest` (dummy) / `razorpay.Client.utility.verify_webhook_signature` (real) — same algorithm either way.
- `orders/domain/state_machine.py` pattern to mirror exactly: `frozenset[str]` of valid statuses, `frozenset[tuple[FromStatus | None, ToStatus]]` transition table (`None` = pre-creation), one `IllegalTransitionError(machine, from_status, to_status)`, one `transition_x(entity, to_status)` function per machine that checks-then-mutates (no partial mutation on illegal calls). Tests (`test_order_state_machine.py`) are exhaustive: every legal pair parametrized to succeed, every illegal `(from, to)` pair computed via `itertools.product` minus the legal set, parametrized to raise.
- `shared/scheduler.py`: `AsyncIOScheduler`, jobs registered in `create_scheduler()`, each opens its **own** `SessionFactory()` session (no request-scoped session to share), queries via one explicitly-justified cross-tenant repository method, applies state-machine transitions per row, **one commit + one log line** at the end (never per-row). Every job function takes an injectable `now_utc: datetime | None = None` for time-travel tests without sleeping.
- `TenantContext` (`shared/tenant.py`): a frozen dataclass, `merchant_id` only. **No base repository class** — enforcement is a per-method convention (`TenantContext` always the first positional arg, query always filters `WHERE merchant_id = tenant.merchant_id`). The one existing cross-tenant exception (`OrderRepository.list_stale_awaiting_payment`) is explicitly docstring-justified as a system job, which is the precedent for a billing sweep's repository method.
- Isolation test pattern (`test_payments.py`): register two independent merchants via the real `/api/v1/auth/register` flow, seed a resource under tenant B, attempt access as tenant A, assert **404** (not 403 — the tenant-scoped query just doesn't find the row).
- **Deviation to flag**: `render.yaml` no longer exists in this repo (removed in commit `85b4bf1` — the backend now deploys on **Railway**, not Render; `backend/README.md`'s "Deployment (Render, free tree)" section is stale). The prompt asks to follow `render.yaml`'s exact secret-declaration discipline — that file is gone, so I'll instead: (1) add the new settings to `shared/config.py`'s `Settings` class with the same "no hardcoded fallback, fails closed / falls back to dummy" comment convention already used for `jwt_secret`/`secrets_encryption_key`, (2) mirror them in `backend/.env.example`, (3) add a row to `backend/README.md`'s env var table (flagging separately that this table itself needs a Railway-vs-Render refresh, out of scope here), and (4) leave the actual values unset in Railway (settable later via the Railway dashboard/CLI) — same spirit as `sync: false`, no committed file to update instead.

### Onboarding gate & WhatsApp intent handling
- `Merchant.onboarding_status` (`identity/domain/models.py`) — 7-state linear machine ending in `"live"`, transitions enforced in `onboarding/domain/state_machine.py`. `live` is reached unconditionally from `catalog_ready` once every *enabled* vertical is ready (`onboarding/domain/onboarding_service.py`'s `try_advance_for_catalog_ready`).
- The gate itself is a raw string comparison, not a named helper: `conversation/domain/handler.py:119-125`, inside `handle_inbound_message()`:
  ```python
  merchant = await MerchantRepository(session).get(tenant.merchant_id)
  if merchant is None or merchant.onboarding_status != "live":
      return HandledMessage(intent=Intent.GREETING, reply_sent=False, skipped_not_live=True)
  ```
  This runs **before** dedup, customer creation, Flow-completion handling, and intent dispatch — an all-or-nothing gate on the whole inbound message. This is the natural place to add a second, structurally separate subscription-status check (own condition, own `skipped_*` reason — not folded into the same `if`), immediately after it.
- `PLACE_ORDER`'s Flow-then-webview logic (`_reply_for_intent`, ~lines 284-329): checks `restaurant_enabled` + `restaurant_ready` → checks a global `BROWSER_LINK` delivery-strategy override → if `waba.whatsapp_flow_id` is set, attempts `sender.send_flow(...)` → on failure or absent flow id, falls through to a plain-text webview link. A Starter-tier gate belongs **inside this same `if` block, before the `waba.whatsapp_flow_id` check** (i.e., alongside the `restaurant_enabled`/`restaurant_ready` precondition) — forcing the webview path deliberately for Starter, not as a third rung of the existing try/fallback chain.
- "Is native Flow available" is currently determined purely off `WhatsAppBusinessAccount` fields (`whatsapp_flow_id`, `flow_private_key_encrypted`), never `Merchant` — the new plan-tier check is an independent, additional condition, not a replacement for these.
- `frontend/src/features/ordering/OrderingPage.tsx` / `ordering_flow/api/router.py`'s `PublicCatalogOut` (`business_name`, `items`, `merchant_whatsapp_number`) has **no** existing plan/branding field — adding one (e.g. `hide_branding: bool`) is a small, additive change to an endpoint that already loads `Merchant` (`_get_merchant_or_404`).
- Order-creation choke point: both the web webview checkout (`ordering_flow/api/router.py`) and the native WhatsApp Flow completion (`conversation/domain/handler.py`'s `_handle_flow_completion`) converge on **`perform_checkout()`** (`ordering_flow/domain/checkout.py`), which calls `OrderRepository.create()` for both COD and online branches. **This is the single correct place to enforce the order cap** — before either `order_repo.create(...)` call, not inside `OrderRepository.create()` itself (used directly by tests to seed data) and not in the state machine (which only governs transitions on an already-created order).
- `MerchantOrderCounter` (`orders/domain/models.py`) — checked directly: this is **only** a per-merchant sequence generator for human-readable `order_number`, unrelated to billing-cycle counting. A cap check needs its own `COUNT(*) WHERE merchant_id=... AND placed_at BETWEEN cycle_start AND cycle_end` query (mirroring the date-range filtering `OrderRepository.get_summary()`/`list()` already do), not a reused counter.
- `Merchant` model (`identity/domain/models.py`) has no subscription-related field today; a 1:1 `subscription` relationship is a clean, additive fit (same shape as the `MerchantOrderCounter` 1:1-by-PK pattern).

### Frontend conventions (`features/settings/`, routing, orders)
- One `SettingsPage.tsx` composed of independent `*Section` components, each backed by its own `use<Thing>.ts` hook file: a module-level `QUERY_KEY` array, one `useQuery` + one `useMutation` pair, mutation input interface declared locally (not in `shared/api/types.ts`), `onSuccess` invalidates `QUERY_KEY`. `usePaymentSettings.ts` is the exact template to copy for `useSubscription.ts`/`useBillingPlans.ts`.
- All HTTP goes through one wrapper, `shared/api/client.ts`'s `apiFetch<T>()` — no per-feature fetch logic, no codegen; response DTOs are **hand-duplicated** in `shared/api/types.ts` with a `*Out` suffix matching the backend Pydantic schema names 1:1.
- `features/orders/statusTransitions.ts` pattern to mirror for `features/billing/subscriptionTransitions.ts`: a `ReadonlySet` of `"${From}->${To}"` string pairs mirroring the backend transition table (comment says so explicitly), one `legalNextStatuses()` filter function, one `STATUS_LABELS` display map — client-side is advisory only, server is the actual authority.
- Dashboard shell: `shared/components/Layout.tsx` already calls `useMe()` and wraps every authenticated route via `<Outlet/>`; a `<TrialBanner/>` slots in directly above `<Outlet/>`, reading a new `useSubscription()`/`useTrialStatus()` hook the same way nav items already read `me.merchant.appointment_enabled`.
- Routing (`App.tsx`): a flat route table with an explicit public/authenticated split (comments call this out). Public pages (`HomePage`, `OrderingPage`) are top-level siblings; authenticated pages nest under `<RequireAuth><Layout>`. New: `/pricing` as a public sibling, `/settings/billing` (or `/billing`) inside the authenticated block.
- **Confirmed via grep**: zero existing hits for `subscription`/`billing`/`plan_tier`/`trial`/`Starter`/`Growth` anywhere in the codebase (front or back) — this is genuinely new territory, not a refactor. No existing dedicated "upsell" component either, but `EmptyState`, `Badge` (tones incl. `gold`/`gray`), and a disabled-control-plus-helper-text pattern (`TestWhatsAppMessageCard.tsx`) are all directly reusable for a new small `UpgradePrompt`/`GrowthLockedCard` component.

### External verification (per §8 open question 3)
Web search against Razorpay's Subscriptions docs (direct fetch of razorpay.com is blocked by this environment's egress proxy, so this is via search-result snippets, not a full doc read) confirms: **a Razorpay Plan is a single-price, single-period, single-interval object** ("period, combined with interval, defines the frequency of the plan"; "you can create multiple plans with different billing cycles and pricing" — i.e., no parameterized interval on one Plan). This settles open question 3: **monthly and annual need two separate Razorpay Plan objects per tier — 6 total**, not one Plan with an interval parameter. Recommend the local `Plan` table also be one row per `(tier, billing_interval)` pair (6 rows), not one row per tier with two ID columns, for a direct 1:1 mapping to Razorpay's own model.

---

## (b) Phase 17 write-up (drafted for `IMPLEMENTATION_PLAN.md`, in its existing format — to be appended verbatim once approved)

> ## Phase 17 — Merchant Subscription & Billing
>
> Orderflow has been free to run on since Phase 0 — every phase so far wires money moving *through* the platform (customer → merchant, Razorpay Payment Links, `payments/`) but none charges the platform's own bill. This phase adds a second, deliberately separate Razorpay integration: platform → merchant recurring subscription billing (Starter/Growth/Pro, monthly or annual), built against a `DummyBillingGateway` exactly as Phase 5 was built against dummy Razorpay Payment Link credentials — no real platform Razorpay account exists yet.
>
> **Deviations from the task brief, and why:**
> - **`render.yaml` no longer exists** (the repo moved to Railway between Phase 16 and now) — platform Razorpay secrets are declared in `shared/config.py` + `.env.example` following the exact fail-closed convention `jwt_secret`/`secrets_encryption_key` already use, with a new row in `backend/README.md`'s env var table, rather than a `render.yaml` entry. Real values are set later directly in Railway, never committed.
> - *(Further deviations will be recorded here once implementation surfaces any — none anticipated beyond the above at design time.)*
>
> **Backend, planned:**
> - New `billing/{domain,adapters,api}` module (hexagonal, matching every other module).
> - `billing/domain/gateway.py`: `BillingGateway` Protocol (`create_subscription`, `verify_webhook`) + `SubscriptionLink`/`VerifiedBillingEvent` dataclasses + `BillingWebhookVerificationError`, mirroring `payments/domain/gateway.py` exactly.
> - `billing/adapters/dummy_gateway.py` / `razorpay_gateway.py` / `gateway_selector.py`: same real-HMAC-in-dummy, prefix-based selection pattern as Phase 5, keyed off `PLATFORM_RAZORPAY_KEY_ID`/`_KEY_SECRET` (one platform-wide pair, no per-merchant resolution).
> - `billing/domain/models.py`: `Plan` (one row per `(tier, billing_interval)`, 6 seeded rows), `Subscription` (1:1 `Merchant`), `BillingEvent` (append-only, `PaymentEvent`-shaped).
> - `billing/domain/state_machine.py`: explicit `SUBSCRIPTION_TRANSITIONS` frozenset + `IllegalTransitionError`, exhaustively unit-tested (every legal + every illegal transition), mirroring `orders/domain/state_machine.py`.
> - `billing/adapters/repository.py`: `PlanRepository` (public, no tenant scope needed), `SubscriptionRepository`/`BillingEventRepository` (`TenantContext`-first convention, no base class).
> - `billing/api/router.py` (`POST /billing/webhook`, unauthenticated, signature-verified, dedupe-by-`provider_payment_id` + illegal-transition-catch, same as `payments/api/router.py`) + `billing/api/dashboard_router.py` (`GET /billing/plans`, `GET /billing/subscription`, `POST /billing/subscribe|change-plan|cancel`, `CurrentTenant`-authenticated).
> - `shared/scheduler.py`: new `sweep_billing_subscriptions` job (own session, cross-tenant query, one commit) handling trial-expiry → Starter-limits and past-due-grace-period → Starter-limits transitions, registered in `create_scheduler()` alongside the existing three jobs.
> - Order-cap enforcement inside `ordering_flow/domain/checkout.py`'s `perform_checkout()`, before either `order_repo.create(...)` call, via a new `OrderRepository.count_since(tenant, cycle_start)` method and an `OrderCapExceededError` both call sites can catch.
> - `conversation/domain/handler.py`: a second, independent gate immediately after the existing `onboarding_status != "live"` check (own `skipped_*` reason, never merged into the same condition); a plan-tier precondition inside `PLACE_ORDER`'s Flow-attempt block, before the `waba.whatsapp_flow_id` check.
> - `ordering_flow/api/router.py`'s `PublicCatalogOut` gains a `hide_branding: bool` field (public-safe — no billing internals leaked).
> - `identity/domain/auth.py`'s register flow creates the `Subscription` row (`trialing`, Growth plan, `trial_ends_at = now + 14d`) in the same transaction as `Merchant`/`StaffUser` — see open question 1.
> - Tests: tenant-isolation on every new repository method, exhaustive state-machine tests, webhook idempotency tests, order-cap enforcement tests (web + Flow paths), Starter-loses-Flow / Growth-keeps-Flow tests, branding-toggle test.
>
> **Frontend, planned:**
> - `features/billing/`: `usePlans.ts`, `useSubscription.ts`, `useSubscribe.ts`/`useChangePlan.ts`/`useCancelSubscription.ts` (mirroring `usePaymentSettings.ts`'s shape), `subscriptionTransitions.ts` (mirroring `statusTransitions.ts`).
> - `PricingPage.tsx` (public route `/pricing`, reusable inside the dashboard too) rendering `GET /billing/plans` — one source of truth for the pricing table.
> - `BillingSettingsPage.tsx` (`/settings/billing`, authenticated) — current plan/status/trial countdown/usage-against-cap, upgrade/downgrade/cancel actions, following `SettingsPage.tsx`'s Card/RHF+Zod/shadcn conventions.
> - `TrialBanner.tsx` inserted into `Layout.tsx` above `<Outlet/>`.
> - `UpgradePrompt.tsx` (new small component, composing `EmptyState`/`Badge`) for Growth-gated feature upsells.
> - `shared/api/types.ts`: `PlanOut`, `SubscriptionOut`, `hide_branding` added to the existing `PublicCatalogOut`.
>
> **Definition of done**: create a subscription against `DummyBillingGateway` for a fresh merchant, simulate a Razorpay-shaped webhook signed with the dummy secret, watch status flip `trialing → active`; hit the order cap on a Starter-limited merchant and confirm the configured behavior fires (see open question — reject vs. soft-block); confirm a Starter merchant's `PLACE_ORDER` always sends the webview link even with a configured `whatsapp_flow_id`, and a Growth/Pro merchant's doesn't; confirm the webview's "Powered by Orderflow" footer appears only for Starter; simulate the trial-expiry sweep and confirm a lapsed trial drops to Starter limits without blocking inbound WhatsApp traffic. `ruff`/`mypy`/backend tests clean; `biome`/typecheck/vitest clean.

---

## (c) Data model & migration (proposed)

```python
# billing/domain/models.py

class Plan(Base):
    __tablename__ = "billing_plans"
    plan_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tier: Mapped[str] = mapped_column(String(16))            # "starter" | "growth" | "pro"
    billing_interval: Mapped[str] = mapped_column(String(16))  # "monthly" | "annual"
    display_name: Mapped[str] = mapped_column(String(64))
    price_inr: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    order_cap: Mapped[int | None] = mapped_column(default=None)  # None = unlimited (Pro)
    whatsapp_flow_enabled: Mapped[bool] = mapped_column(default=False)
    branding_required: Mapped[bool] = mapped_column(default=True)
    razorpay_plan_id: Mapped[str | None] = mapped_column(String(255), default=None)
    __table_args__ = (UniqueConstraint("tier", "billing_interval"),)

class Subscription(Base):
    __tablename__ = "subscriptions"
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), primary_key=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("billing_plans.plan_id"))
    status: Mapped[str] = mapped_column(String(16))  # trialing|active|past_due|canceled|expired
    trial_ends_at: Mapped[datetime | None] = mapped_column(default=None)
    current_period_start: Mapped[datetime | None] = mapped_column(default=None)
    current_period_end: Mapped[datetime | None] = mapped_column(default=None)
    past_due_since: Mapped[datetime | None] = mapped_column(default=None)
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at / updated_at: as elsewhere

class BillingEvent(Base):
    __tablename__ = "billing_events"
    billing_event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    provider: Mapped[str] = mapped_column(String(32))          # "razorpay" | "dummy"
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), index=True, default=None)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(255), default=None)
    event_type: Mapped[str] = mapped_column(String(64))        # subscription.activated | .charged | .pending | .halted | .cancelled | payment.failed | webhook_received_duplicate | order_cap_exceeded
    raw_payload: Mapped[str | None] = mapped_column(Text, default=None)
    received_at: Mapped[datetime] = mapped_column(default=...)
```

`billing/domain/state_machine.py`:
```
SUBSCRIPTION_TRANSITIONS = frozenset({
    (None, "trialing"),
    ("trialing", "active"),        # subscribe / mandate confirmed before trial ends
    ("trialing", "expired"),       # trial sweep, no active subscription
    ("active", "past_due"),        # payment.failed
    ("past_due", "active"),        # recovered charge
    ("past_due", "canceled"),      # grace period exceeded / provider halted
    ("active", "canceled"),        # user-initiated, effective at period end
    ("expired", "active"),         # subscribes after trial lapse
    ("canceled", "active"),        # re-subscribes later
})
```
(Exact table to be finalized against real Razorpay webhook semantics during implementation — `subscription.halted` maps to `past_due → canceled` after Razorpay's own retry exhaustion, per open question 2 below.)

Migration: `billing_plans`, `subscriptions`, `billing_events` tables; seed migration/script inserting the 6 `Plan` rows from the pricing table in §1 of the task brief.

---

## (d) Open questions — answered/recommended (confirm before implementation)

1. **Trial start point**: recommend **`registered`** (immediately at signup), not `live`. Reasoning: onboarding's `live` gate and the subscription gate are independent by design (§2's own instruction) — no order can flow before `live` regardless of subscription status, so starting the trial clock at `registered` doesn't leak any value early, and it matches the plain "14-day free trial" mental model a merchant expects from the moment they sign up rather than a clock that silently starts whenever they happen to finish onboarding (which could be same-day or a week later, arbitrarily). Mechanically simpler too: `Subscription` created in the same transaction as `Merchant`/`StaffUser` in `identity/domain/auth.py`'s register flow.

2. **`past_due` behavior**: recommend a **4-day grace period** (roughly matching Razorpay's own UPI Autopay/eMandate retry cadence) during which the merchant keeps full paid-tier access plus a dashboard warning banner; if unrecovered after 4 days, drop to **Starter limits** (same landing spot as an expired trial) rather than a harder lockout — consistent with "don't cut off a live restaurant" from §1. `subscription.halted` (Razorpay gives up retrying) transitions straight to `canceled`→Starter-limits without waiting out the grace period, since Razorpay itself has already exhausted retries by the time it sends that event.

3. **Annual billing shape**: confirmed via search against Razorpay's docs — **two separate Plan objects per tier are required** (6 total), not one parameterized Plan. Local `Plan` table mirrors this 1:1 (one row per `(tier, interval)`).

4. **Order-cap counting window**: recommend `current_period_start`/`current_period_end` from `Subscription` once a real billing cycle exists (populated from Razorpay's `subscription.charged` webhook payload), falling back to a **calendar-month window** whenever there is no billing period yet — during `trialing` (single 14-day window, no reset needed given trial length is well under a month) and once lapsed to Starter-limits with no active subscription. This avoids a period-less state ever having an undefined cap window.

5. **New, not in the original brief — order-cap enforcement mechanism** (§2 explicitly asks for a recommendation): recommend **soft-block, not hard-reject**. Never fail a customer's in-progress WhatsApp/webview checkout because of the merchant's billing state — that punishes the customer for the merchant's plan choice and risks losing an order Orderflow's own pilot goal depends on ("no restaurant staff manual intervention needed to take the order"). Instead: surface a prominent dashboard banner + (future) email once at/over cap, log a `BillingEvent(event_type="order_cap_exceeded")` per over-cap order for audit/dunning purposes, and let the order complete. This is a dunning signal, not a gate — matches the same philosophy already chosen for expired trials and past_due.

**Additional flag (not an open question, but surfaced during research)**: `backend/README.md`'s deployment section still describes Render; the repo actually deploys on Railway (render.yaml was removed in `85b4bf1`). This phase's env-var documentation will go into the existing (stale) README table rather than reintroducing `render.yaml` — flagging that the README's Render framing itself is out of date is a separate, smaller cleanup outside this ticket's scope, noted here so it isn't silently "fixed" by implication.

---

## Implementation approach (once confirmed)

1. Migration + `billing/domain/models.py` + `billing/domain/state_machine.py` (+ exhaustive tests, no DB).
2. `billing/adapters/{repository,dummy_gateway,razorpay_gateway,gateway_selector}.py` (+ tenant-isolation tests).
3. `billing/api/{router,dashboard_router,schemas}.py`, wired into `app.py`/`dashboard_api/api/router.py`.
4. `shared/config.py` + `.env.example` + `backend/README.md` env var row (platform Razorpay secrets, fail-closed).
5. `shared/scheduler.py`'s `sweep_billing_subscriptions` job.
6. Gates: order cap in `perform_checkout()`; subscription gate in `conversation/domain/handler.py` (separate from the `live` check); Flow-vs-webview tier check in `_reply_for_intent`; `hide_branding` on `PublicCatalogOut`.
7. `ARCHITECTURE.md` §2 update (retire the stale "no current pilot need" feature-flags note).
8. Frontend: `features/billing/` hooks + `PricingPage`/`BillingSettingsPage`/`TrialBanner`/`UpgradePrompt`, routes in `App.tsx`, `SettingsPage.tsx` nav link.
9. Full test suite (backend `pytest`/`ruff`/`mypy`, frontend `vitest`/`biome`/`tsc`) + live walkthrough per the Definition of done above.
10. Docs: `IMPLEMENTATION_PLAN.md` Phase 17 entry (finalized from §b above, updated with any real deviations found while building), `ARCHITECTURE.md` update.

**Risks**: (a) subscription state machine correctness under concurrent/duplicate webhooks — mitigated by mirroring `PaymentEvent`'s proven dedupe pattern exactly; (b) two independent gates (onboarding `live`, subscription status) in the same handler function risking accidental conflation — mitigated by keeping them as clearly separate `if` blocks with distinct `skipped_*` reasons, tested independently; (c) order-cap query performance at scale — not a concern at pilot scale (same reasoning `TECH_STACK.md` already applies to APScheduler-over-Celery).

## Subtask checklist
- [ ] User confirms this write-up (data model, Phase 17 doc, open-question recommendations) before any code is written.
- [ ] Migration + `billing` domain models + state machine + tests
- [ ] `billing` adapters (repository, dummy/real gateway, selector) + tenant-isolation tests
- [ ] `billing` API (webhook + dashboard router) + schemas
- [ ] Platform Razorpay config + env var docs
- [ ] Scheduler sweep job
- [ ] Order-cap gate in checkout
- [ ] Subscription gate in conversation handler (separate from `live`)
- [ ] Flow-vs-webview tier gate
- [ ] `hide_branding` on public catalog DTO
- [ ] `ARCHITECTURE.md` §2 update
- [ ] Frontend: hooks, PricingPage, BillingSettingsPage, TrialBanner, UpgradePrompt, routes
- [ ] Full backend + frontend test/lint/typecheck pass
- [ ] Live walkthrough per Definition of done
- [ ] `IMPLEMENTATION_PLAN.md` Phase 17 entry finalized
- [ ] Trello card moved through To Do → In Progress → In Review → Done with matching comments
- [ ] Pre-merge audit pass (per CLAUDE.md's "Ongoing sync + auditing")

## Progress Log

**2026-09-07** — Pre-coding research complete (3 parallel Explore subagents tracing `payments/`, onboarding/conversation gating + order-cap choke point, and frontend `settings`/routing conventions, plus direct reads of `ARCHITECTURE.md`/`TECH_STACK.md`/`IMPLEMENTATION_PLAN.md`/the brief, plus one external check confirming Razorpay's Plan-per-interval requirement). Trello card #49 created in "To Do". This `PLAN.md` drafted with the full data model, a draft Phase 17 doc, and recommendations on all four open questions plus the order-cap-enforcement discussion point. **No implementation code written yet** — awaiting explicit user confirmation per the task's own instruction. No deviations from the task brief found beyond the `render.yaml`→Railway migration noted above.
