# Orderflow — Vertical Toggle / Multi-Select Onboarding Plan

Plan-only document, written before any code, per the same convention `MULTI_VERTICAL_PLAN.md` established for Phase 10. It extends `IMPLEMENTATION_PLAN.md`'s Phase 10 (`Merchant.vertical`, a single mutually-exclusive enum chosen once at onboarding and never changed) into an **additive, always-editable model**: a merchant can run restaurant ordering, appointment booking, or both, and can add a second vertical later from Settings without ever having to re-answer the first one. Read `IMPLEMENTATION_PLAN.md`'s Phase 10 entry and `MULTI_VERTICAL_PLAN.md` first — this plan is the next increment on top of them, not a rewrite from scratch.

## Why this supersedes Phase 10's "exactly one, forever" model

Phase 10 deliberately made `vertical` an immutable, mutually-exclusive choice (`MerchantRepository.set_vertical` raises on a second call; the wizard step renders read-only once answered) — the right call at the time, matching the ask that produced it. The new ask is different: a merchant should be able to pick both restaurant and appointment booking **upfront**, and a merchant who picked only one should be able to **add the other later from Settings**, not just at registration. That's a strictly more general model than "exactly one, forever," so this plan replaces the single `vertical` column with two independent booleans rather than layering a second selection mechanism on top of the enum.

## Data model change

- Drop `Merchant.vertical: str | None` (the `MerchantVertical` enum stays, but as a typed parameter — "which vertical" — not a stored single value).
- Add `Merchant.restaurant_enabled: bool` (default `False`) and `Merchant.appointment_enabled: bool` (default `False`).
- **Domain invariant, enforced in exactly one place** (`identity/domain/models.py`'s `validate_vertical_flags`): `restaurant_enabled` and `appointment_enabled` can't both be `False`. Both the onboarding entry point and the Settings entry point call the same repository method (`MerchantRepository.set_vertical_flags`), which runs this validator before writing — per the ask, "no separate code path or weaker validation just because it's onboarding."
- Migration backfills every existing merchant from their old `vertical` value (`restaurant` → `restaurant_enabled=True`; `appointment` → `appointment_enabled=True`) before dropping the column, so no merchant is ever left with both flags `False`.

## The immutability rule is retired, not replaced

Phase 10's "no admin ability to switch a merchant's vertical after onboarding" is explicitly reversed by this ask (the whole point of the Settings add-on path is to change the flags after onboarding). So `set_vertical_flags` has no one-time/409 guard at all — it's just "validate the invariant, write the two columns" — called by:
1. The onboarding wizard's first step (`PUT /api/v1/onboarding/verticals`), the first time a merchant answers it.
2. The same endpoint, called again later from Settings, to add (or in principle change) a vertical.

One endpoint, one repository method, one validator — not two code paths that could drift.

## The "don't show an empty flow" rule is enforced once, dynamically — not by locking state

The ask's core UX rule — a vertical that's flagged on but has zero menu items/services behind it must never be presented to a WhatsApp customer — already has a natural home: `conversation/domain/handler.py`'s menu-and-reply builder. Today it gates each intent on `merchant.vertical == X`; this plan changes that gate to `merchant.X_enabled AND X_is_ready` (`restaurant` ready = ≥1 available `Item`; `appointment` ready = ≥1 active `AppointmentService`), computed fresh on every inbound message via the same repositories the onboarding gate already uses. This one change covers both entry points automatically:
- **Onboarding**: a merchant can't reach `onboarding_status == "live"` while any *enabled* vertical isn't ready (extends the existing `try_advance_for_catalog_ready` gate, see below).
- **Settings add-on**: a merchant who's already `live` and flips on a second vertical doesn't need any onboarding-status change at all — the WhatsApp menu simply won't offer that vertical's options until its readiness gate is met, exactly the same check, no new state to track.

This also **overrides `MULTI_VERTICAL_PLAN.md`'s Decision 5** ("appointment services are optional by design, no required gate") — under the additive model, an enabled-but-empty appointment vertical is exactly the "empty flow" the ask says never to show, so `AppointmentService` becomes a required-if-enabled gate, symmetric with `Item` for restaurant. `AppointmentService` rows stay optional in the sense that a merchant can still add just one generic service and be done — the model itself doesn't change, only whether zero rows is good enough to go live/show the vertical in WhatsApp.

## Onboarding status machine — no new states needed

`ONBOARDING_STATUSES` (`registered → vertical_selected → meta_connected → whatsapp_verified → profile_completed → catalog_ready → live`) is left exactly as-is, names included — a rename buys clarity but multiplies the blast radius (migration data, every test, every frontend string) for no behavior change, so it's skipped. What changes is purely the *gate logic* at `profile_completed → catalog_ready`: instead of "restaurant needs ≥1 item, appointment needs nothing," it becomes "every *enabled* vertical needs its own readiness gate satisfied" (trivially true for a vertical that isn't enabled). Still routed through the same intermediate `catalog_ready` status before cascading to `live`, preserving the "strictly linear, no step-skipping" invariant `MULTI_VERTICAL_PLAN.md` established.

## Onboarding wizard step sequence

Old (single-choice): Business type → Connect WhatsApp → Business details → (Add an item | Add a service) → FAQs → Go live.

New (multi-select), step 0 becomes checkboxes instead of two mutually-exclusive cards, and step 3 expands to **one setup step per selected vertical, run one after another**, before FAQs/Go live:

```
0. Business type (checkboxes: Restaurant / Orders, Appointments — ≥1 required to continue)
1. Connect WhatsApp
2. Business details
3. Add an item          -- only if restaurant_enabled
4. Add a service         -- only if appointment_enabled (step 3 if restaurant wasn't selected)
5. FAQs (optional)
6. Go live
```

**Order decision: restaurant-then-appointment, always** (not "whichever was checked first"). Tracking UI click-order and threading it through a page reload (the wizard already supports navigating away and back mid-flow, driven by server state) adds real complexity for no product value the ask actually asks for — it explicitly offers the fixed-order fallback as an equally acceptable choice ("or default restaurant-then-appointment for consistency"), so this plan takes the simpler, more robust option. If a merchant selects only one vertical, its single setup step appears at position 3, same as today.

Because the backend still exposes only one `catalog_ready`-equivalent gate (not a per-vertical status), the wizard determines *which* per-vertical step to show from `OnboardingStatusOut`'s existing `has_available_item`/`has_available_service` fields directly, not from `onboarding_status` alone: while `onboarding_status == "profile_completed"`, the furthest-reached step is the first selected vertical's setup step whose readiness flag is still `False`; once every selected vertical is ready, the gate cascades server-side straight through `catalog_ready` to `live` (same as today), and the wizard jumps to FAQs/Go-live. This needs no new backend fields — the two `has_available_*` booleans already exist and are exactly the per-vertical readiness signal.

The vertical-select step itself stops being permanently read-only (Phase 10's UI special-case): since the flags are genuinely editable later via Settings, the wizard step behaves like every other step — click back into it, resubmit, no 409. This removes a UI special case that no longer matches the underlying data model.

## API surface changes

- `PUT /api/v1/onboarding/vertical` (single value, one-time) → `PUT /api/v1/onboarding/verticals` (`{restaurant_enabled, appointment_enabled}`, callable any number of times, 422 if both `false`). Used by both the onboarding wizard and a new Settings "Business types" section — literally the same request.
- `GET /api/v1/onboarding/status` (`OnboardingStatusOut`): `vertical: str | None` → `restaurant_enabled: bool, appointment_enabled: bool`.
- `GET /api/v1/auth/me` (`MerchantOut`): same field swap, since `Layout.tsx`'s nav reads it from there.
- `appointment_flow/api/router.py`'s public-booking-webview 404 gate: `merchant.vertical != APPOINTMENT` → `not merchant.appointment_enabled`.
- `identity/api/router.py`'s appointment-service create/update endpoints gain the same "try to advance the onboarding gate" call `catalog/api/router.py`'s item create/update endpoints already make — needed now that appointment readiness is a real gate, not a no-op.
- `shared/scheduler.py`'s reminder scan: `MerchantRepository.list_by_vertical(APPOINTMENT)` → `list_enabled_for_vertical(APPOINTMENT)` (same shape, now reads the boolean column instead of the enum column).

## Settings: the add-on-later entry point

New Settings section ("Business types"), two checkboxes bound directly to `restaurant_enabled`/`appointment_enabled`, submitting through the same `PUT /api/v1/onboarding/verticals` the wizard uses. Turning one on doesn't force the merchant back into the onboarding wizard — they land back on Settings, and the new vertical's Catalog/Services page and dashboard nav tab appear immediately (nav already reads the flags), while WhatsApp stays silent about it until the readiness gate is met (previous section). The existing per-vertical Settings gating (WhatsApp Flow setup cards, appointment availability-hours section) changes from `vertical === 'x'` (mutually exclusive) to `x_enabled` (independent — both can render at once).

## Phases

### Phase T1 — Data model + shared validation
Migration (add both boolean columns + backfill + drop `vertical`); `identity/domain/models.py` (`validate_vertical_flags`, `NoVerticalSelectedError`); `identity/adapters/repository.py` (`set_vertical_flags`, `list_enabled_for_vertical`, drop `set_vertical`/`VerticalAlreadySetError`). Tests: invariant rejection, backfill correctness, independent read/write of each flag.

### Phase T2 — Onboarding gate becomes multi-vertical-aware
`onboarding/domain/onboarding_service.py`: `try_advance_for_catalog_ready` checks every *enabled* vertical's readiness (extract `restaurant_ready`/`appointment_ready` helpers, reused by Phase T4's WhatsApp gate). `identity/api/router.py`'s appointment-service endpoints call the gate. Tests: both-enabled-both-ready cascades to live; both-enabled-one-ready stays at `catalog_ready`; single-vertical behavior is an unchanged special case of the general rule.

### Phase T3 — API surface: multi-select endpoint + schemas
`PUT /api/v1/onboarding/verticals`, `OnboardingStatusOut`/`MerchantOut` field swap. Tests: 422 on both-false, repeated calls (onboarding then later from Settings) both succeed, no 409 anywhere.

### Phase T4 — WhatsApp: additive menu, empty-flow guard
`conversation/domain/handler.py`'s menu builder and per-intent reply branches become additive on `(enabled AND ready)` instead of exclusive on one vertical; `appointment_flow/api/router.py` gate swap; `shared/scheduler.py` method rename. Tests: both-enabled merchant's menu offers all four options; an enabled-but-not-ready vertical is silently absent from the menu (the empty-flow guard, exercised directly, not just inferred from Phase T2's onboarding-gate tests).

### Phase T5 — Frontend: onboarding multi-select + Settings add-on + nav
Types, `Layout.tsx` (additive nav), `OnboardingPage.tsx` (checkboxes, dynamic per-vertical step sequence, editable vertical step), new Settings "Business types" section, existing Settings vertical-gated sections switched to independent flags. Tests per the existing per-page convention (`OnboardingPage.test.tsx`, `Layout.test.tsx`, `SettingsPage.test.tsx`).

### Phase T6 — Docs
`ARCHITECTURE.md` (§1 the two flags, §5 the gate rule, §6/§9c the additive WhatsApp menu, §9b the checkbox step); `IMPLEMENTATION_PLAN.md` gains a "Phase 11" after-the-fact entry once T1–T5 are built and tested, same convention Phases 5–10 already follow.

## Explicitly unchanged / out of scope

- No third vertical — still exactly two booleans, not a set/list, matching `MULTI_VERTICAL_PLAN.md`'s existing "more than two verticals is explicitly out of scope."
- No UI path to *disable* an already-live vertical that has existing orders/appointments behind it — the two Settings checkboxes can turn a flag on or off (the invariant validator is symmetric), but this plan doesn't add any warning/confirmation UX for the disable direction, since the ask is specifically about adding verticals, not removing them. Worth a follow-up if a real merchant hits it.
- `StaffResource`/multi-provider calendars, payment-for-appointments, POS sync: unchanged, still out of scope per `MULTI_VERTICAL_PLAN.md`.
