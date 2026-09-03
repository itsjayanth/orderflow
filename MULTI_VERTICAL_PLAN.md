# Orderflow — Multi-Vertical Implementation Plan

Plan-only document, per the request that produced it — **nothing here has been built yet**. It extends `IMPLEMENTATION_PLAN.md`'s MVP (Phases 1–9, all done) with the two-vertical requirement: a merchant is either `restaurant` or `appointment`, chosen once at onboarding, and every surface (WhatsApp conversation, dashboard) adapts to it. Read `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, and `docs/project-brief.txt` first — this plan assumes them.

## Read this first: most of the appointment domain already exists

Before phasing anything, a repo audit turned up something that changes the shape of this plan significantly: **appointment booking is not a green-field build.** Commits `#16`–`#19` already shipped a full appointment vertical — as an *additive, opt-in feature* (`Merchant.appointment_booking_enabled: bool`, default off) that runs **alongside** restaurant ordering for any merchant who flips it on, not instead of it. Concretely, already built and working:

| Area | What exists today |
|---|---|
| Domain | `appointments/domain/models.py`: `Appointment`, `AppointmentService`, `StaffResource` (schema-ready, unused), `MerchantAvailability`, `AppointmentReminder`, `MerchantAppointmentCounter`. `appointments/domain/state_machine.py`: explicit transition table (`requested → confirmed → completed`, `requested/confirmed → cancelled`), unit-testable in isolation — same pattern as `orders/domain/state_machine.py`. |
| Adapters/API | `appointments/adapters/repository.py` (overlap-safe booking, dashboard listing, status transitions), `appointments/api/router.py` (dashboard CRUD + status updates). |
| Booking flow | `appointment_flow/` (`availability.py` — fixed weekly-recurring slots via `MerchantAvailability`, sliced into `slot_duration_minutes` increments minus buffered bookings; `booking.py` — `perform_booking`, overlap/past-date guarded; `reminders.py`), public API in `appointment_flow/api/router.py`. |
| WhatsApp | `flows/domain/appointment_booking.py` + `flows/assets/appointment_flow.json` (native in-chat booking Flow), `conversation/domain/handler.py`'s `BOOK_APPOINTMENT` intent and `_handle_appointment_flow_completion`, `shared/interaction_mode.py` (feature-agnostic `WHATSAPP_FLOW`/`BROWSER_LINK` switch — already handles both `ORDER_PLACING` and `APPOINTMENT_BOOKING` as parallel `Feature`s). |
| Notifications | Lifecycle events (`AppointmentRequested`, etc.) wired through the same `notifications/` bus as orders; `shared/scheduler.py`'s `send_due_appointment_reminders` sends a pre-appointment reminder per `Merchant.reminder_offsets_hours` — the "new, orders don't have this" item from the original ask, done. |
| Payment | `Appointment.payment_status` (`not_required`/`pending`/`paid`/`failed`) exists as a **schema-only placeholder** — no gateway wired to it. Matches this plan's recommendation (see Decisions) without needing a change. |
| Frontend | `features/appointments/` (dashboard), `features/booking/` (public booking webview), a Settings-page toggle for `appointment_booking_enabled` + reminder-offset config. |
| Nav | `Layout.tsx`'s `NAV_ITEMS` is static — **Orders and Appointments both always show**, regardless of the toggle. |

So Section 1 (data model) and Section 3 (booking flow) of the original ask are largely **done**, and this plan's real job is narrower and different from "build an appointment vertical": **convert an additive opt-in feature into a mutually-exclusive vertical**, then do the parts that genuinely don't exist yet — nav/onboarding/WhatsApp-menu exclusivity, removing "Talk to us," and Menu-vs-Services labeling. Phases below are scoped accordingly; several are refactors of existing gating logic, not new domain code.

One correction to make while here: `Merchant`'s business-detail columns are *already* vertical-neutral (`business_address_*`, `business_category`, `license_no` — renamed off `kitchen_*` per `IMPLEMENTATION_PLAN.md`'s Phase 8 deviation note), so the "kitchen details doesn't make sense for a consultant" concern the original ask raised is already resolved at the schema level. What still hard-codes restaurant framing is copy/labels in the wizard UI and the WhatsApp intent menu, not the data model.

---

## Decisions (per the original ask's "decide" items)

1. **Catalog/Item vs. Service — keep separate, don't generalize.** Already how it's built (`Item` for restaurant, `AppointmentService` for appointment, no shared base). Confirmed as the right call: a cart/quantity concept doesn't fit a time-slot booking, and the two entities' fields already diverge (`price` required vs. optional, `duration_minutes` has no order-side analogue). One dashboard *page* per vertical (`CatalogPage.tsx` / a new `ServicesPage.tsx`), sharing low-level list/row/form UI atoms where shapes coincide, not one vertical-branching mega-component — the underlying data hooks are genuinely different (`useItems` vs. a new `useServices`), so branching inside a single page buys nothing.
2. **Availability model — fixed weekly slots, no calendar sync.** Already built this way (`MerchantAvailability` + `get_available_slots`). No change needed; confirming it as the v1 scope per the original ask's "keep it simple" instruction.
3. **Payment for appointments — stays out of scope, deposit placeholder untouched.** The schema-only `payment_status` placeholder already exists and is never routed to a gateway. Recommend leaving it exactly as-is (don't remove it, don't wire it) — it costs nothing sitting idle and saves a future migration if a paid-consultation vertical variant ever needs it.
4. **Vertical selection step ordering.** Put it as the *very first* wizard step — before "Connect WhatsApp" — not merely "before business details" as the original ask's minimum bar. Nothing about connecting a WhatsApp number differs by vertical, but the step's own copy ("What kind of business is this?") reads oddly wedged after a technical setup step, and every step after it (including which WhatsApp Flow gets offered, see Phase M4) needs to know the vertical already. New `Merchant.onboarding_status` value: `vertical_selected`, inserted right after `registered`.
5. **`catalog_ready`-equivalent gate for the appointment vertical — no required gate.** `AppointmentService` rows are optional by the existing model's own design (a merchant with zero rows just has one generic appointment type — see its docstring). Requiring "at least one service" before going live would contradict that and add friction the appointment vertical doesn't need. So: restaurant vertical keeps today's `catalog_ready` gate (≥1 available `Item`) unchanged; appointment vertical cascades `profile_completed → live` directly, with an *optional* "Add a service" wizard step (same non-blocking pattern the existing `AddFAQStep` already uses — "entirely optional and won't hold up going live").
6. **Enum, not a free string, for `vertical`.** A `StrEnum`/Postgres enum with exactly `restaurant`/`appointment`, matching the original ask's "more than two verticals is explicitly out of scope" — makes adding a third vertical a visible migration, not a silent string typo.

---

## Phase M1 — Merchant.vertical: migration + state machine

Foundational column everything else gates on. Small on purpose — this phase adds the field and the new onboarding state, nothing else yet.

1. **Migration** — `identity/domain/models.py`: add `MerchantVertical(StrEnum)` (`RESTAURANT = "restaurant"`, `APPOINTMENT = "appointment"`); `Merchant.vertical: Mapped[str | None]`, nullable initially (existing merchants haven't chosen one). Backfill data migration in the same Alembic revision: for every existing row, set `vertical = 'appointment' if appointment_booking_enabled else 'restaurant'` — preserves current behavior for pilot merchants who already opted into the toggle. `ONBOARDING_STATUSES` gains `"vertical_selected"` immediately after `"registered"`.
2. **Domain** — `onboarding/domain/state_machine.py` needs no code change (it derives `ONBOARDING_TRANSITIONS` from the tuple, per its own comment) but its transition-table unit test must be regenerated for the new adjacent pair. `onboarding/domain/onboarding_service.py`: new `advance_after_vertical_selected(merchant)` — idempotent, same shape as the existing `advance_after_whatsapp_connected`.
3. **Adapters** — `identity/adapters/repository.py`'s `MerchantRepository` gains `set_vertical(tenant, vertical)` — raises if `merchant.vertical is not None` (immutable once set, per the original ask's "no admin ability to switch after onboarding" — enforced structurally, not just by UI omission).
4. **API** — `PUT /api/v1/onboarding/vertical` (body: `{"vertical": "restaurant" | "appointment"}`) in `onboarding/api/router.py` — calls `set_vertical` then `advance_after_vertical_selected`; 409 if already set.
5. **Backend tests** — onboarding state-machine transition table (new pair + every illegal pair involving it); `set_vertical` immutability (second call raises); endpoint test (happy path advances status; repeat call 409s); migration backfill logic covered by a repository-level test seeding both toggle states pre-migration-equivalent data.
6. **Frontend** — none yet; this phase is backend-only, mirroring how Phase 1 of the original MVP plan landed schema+API before UI.
7. **Frontend tests** — none yet.

**Definition of done**: `curl -X PUT .../onboarding/vertical -d '{"vertical":"appointment"}'` on a freshly-registered merchant advances `onboarding_status` to `vertical_selected` and returns it in `GET /onboarding/status`; a second call to the same endpoint 409s.

---

## Phase M2 — Onboarding wizard: vertical step + branching copy

1. **Migration** — none (M1 covered it).
2. **Domain** — none beyond M1.
3. **Adapters** — none beyond M1.
4. **API** — none beyond M1 (already shipped).
5. **Backend tests** — none new.
6. **Frontend** — `features/onboarding/OnboardingPage.tsx`: new `VerticalSelectStep` component as step 0 (two large choice cards — "Restaurant" / "Appointment Booking" — each with a one-line description), calling the M1 endpoint on selection; every existing step shifts up one index. Unlike every other step, once past `vertical_selected` this step renders **read-only** (shows the chosen vertical, no way to change it) rather than the usual "click back into a completed step to edit" behavior every other step supports — the original ask treats this as fixed at registration, and the immutable-backend guard (M1) would just 409 a resubmit anyway, so the UI shouldn't offer it. `BusinessDetailsStep`: branch copy only (no field changes — the schema's already vertical-neutral per the corrected assumption above) — e.g. "Business category" placeholder reads "Cuisine type (e.g. North Indian, bakery)" for restaurant vs. "Service category (e.g. salon, dental clinic)" for appointment.
7. **Frontend tests** — `OnboardingPage.test.tsx`: renders `VerticalSelectStep` first for a brand-new merchant; submitting a vertical choice advances to the (shifted) WhatsApp-connect step; the vertical step renders read-only once already answered; `BusinessDetailsStep` shows the right copy for each vertical (two render-only assertions, no new logic to test).

**Definition of done**: registering a new merchant lands on the vertical-choice screen before anything else; picking "Appointment Booking" and clicking through the rest of the wizard shows branched business-details copy; reloading mid-wizard still shows the vertical step as already-answered and non-editable.

---

## Phase M3 — Menu vs. Services + the `catalog_ready`-equivalent gate

1. **Migration** — none.
2. **Domain** — `onboarding/domain/onboarding_service.py`: `try_advance_for_catalog_ready` becomes vertical-aware — restaurant path unchanged (≥1 available `Item`); appointment path: `profile_completed → live` fires directly with no precondition check (per Decision 5), i.e. effectively the same cascade `catalog_ready → live` already does today, just reached without a gate.
3. **Adapters** — none beyond existing `ItemRepository`/`AppointmentService`-side queries.
4. **API** — no new endpoints; wire the vertical-aware gate call into the existing `catalog/api/router.py` create/update handlers (restaurant only — the appointment path doesn't need any endpoint to trigger it, since it's ungated).
5. **Backend tests** — `test_onboarding_flow.py`: appointment-vertical merchant reaches `live` immediately after `profile_completed` with zero `AppointmentService` rows; restaurant-vertical merchant's existing catalog-ready test is unchanged (regression check, not new coverage).
6. **Frontend** — new `features/services/ServicesPage.tsx` (appointment vertical's dashboard page — name, duration, optional price, active toggle; same table+form shape as `CatalogPage.tsx` but its own feature slice, per Decision 1), `useServices.ts`/`useCreateService.ts`/`useUpdateService.ts` hooks over the existing `AppointmentService` API. Onboarding wizard's step 2 branches: `AddItemStep` (restaurant, unchanged) vs. new `AddServiceStep` (appointment, explicitly optional — "Add a service (optional)," mirrors `AddFAQStep`'s non-blocking framing). Dashboard nav (`Layout.tsx`): `NAV_ITEMS` becomes a function of `merchant.vertical` from `useMe()` — restaurant shows `Orders` + `Catalog`; appointment shows `Appointments` + `Services`; every vertical-neutral item (`Dashboard`, `FAQs`, `Customers`, `Onboarding`, `Settings`) stays for both. No flash-then-hide: nav renders nothing vertical-specific until `useMe()` resolves, then exactly one pair appears — never both, never neither.
7. **Frontend tests** — `Layout.test.tsx`: renders `Orders`/`Catalog`, never `Appointments`/`Services`, for a restaurant merchant, and vice versa. `ServicesPage.test.tsx`: mirrors `CatalogPage.test.tsx`'s existing add/list coverage. `AddServiceStep` renders and is skippable without blocking the "Go live" step.

**Definition of done**: an appointment-vertical merchant reaches "You're live!" having never seen a Catalog/Menu step, can add a service from the new Services page, and their dashboard nav shows Appointments+Services, never Orders+Catalog; a restaurant-vertical merchant's nav and flow are pixel-for-pixel what they are today (regression, not just new behavior).

---

## Phase M4 — WhatsApp: exclusive intent menu, drop "Talk to us," appointment tracking

The highest-risk phase — it changes behavior for every live merchant's WhatsApp conversation, restaurant and appointment alike (removing "Talk to us" affects both).

1. **Migration** — none.
2. **Domain** — `conversation/domain/intents.py`: remove `Intent.TALK_TO_RESTAURANT` and its keyword-dict entry entirely (not conditionally — per the original ask, for both verticals). Add `Intent.TRACK_APPOINTMENT` with keywords checked *before* `BOOK_APPOINTMENT`'s broad "appointment"/"booking" keywords (same ordering fix `intents.py` already applies to `TRACK_ORDER` vs. `PLACE_ORDER`, so "check my appointment" doesn't get swallowed by `BOOK_APPOINTMENT`'s "appointment" keyword).
3. **Adapters** — `appointments/adapters/repository.py`: new `list_for_customer(tenant, customer_id, limit)`, mirroring `OrderRepository.list_for_customer` exactly (same signature shape, ordered by `requested_at desc`).
4. **API** — no new HTTP endpoints (WhatsApp-side only). `conversation/domain/handler.py`:
   - `_menu_options()` stops being additive (`appointment_booking_enabled` flag) and becomes exclusive on `merchant.vertical`: restaurant → `[PLACE_ORDER, TRACK_ORDER]`; appointment → `[BOOK_APPOINTMENT, TRACK_APPOINTMENT]`; both then optionally append `FAQ_MENU` if the merchant has active FAQs. `TALK_TO_RESTAURANT` row removed unconditionally.
   - `_reply_for_intent`: `PLACE_ORDER`/`TRACK_ORDER` branches only fire for `vertical == "restaurant"`; `BOOK_APPOINTMENT` branch's existing `and appointment_booking_enabled` guard becomes `and merchant.vertical == "appointment"`; new `TRACK_APPOINTMENT` branch (appointment vertical only) calls the new `list_for_customer` and formats a reply mirroring `_track_order_reply`. A customer on the "wrong" vertical typing e.g. "track my order" falls through to the greeting menu exactly like an unrecognized message does today — no special error copy needed, matches the existing fallback behavior for a disabled feature.
   - `TALK_TO_RESTAURANT` branch in `_reply_for_intent` deleted outright.
   - Settings page's WhatsApp Flow setup: gate the "Order Flow" setup card to restaurant merchants and the "Appointment Flow" card to appointment merchants (currently both are presumably offered regardless — confirm during implementation and gate if so), so a merchant can't provision a Flow their vertical will never send.
5. **Backend tests** — `test_intents.py`: drop all `TALK_TO_RESTAURANT` cases, add `TRACK_APPOINTMENT` classification cases including the order-sensitivity check ("my appointment status" doesn't misfire as `BOOK_APPOINTMENT`). `test_conversation_handler.py`: per-vertical menu-options tests (no "Talk to us" row ever, in either vertical); a restaurant merchant messaged with `BOOK_APPOINTMENT`'s button id falls through to the menu, and vice versa for appointment merchants and `PLACE_ORDER`; new `TRACK_APPOINTMENT` handler test (empty history, most-recent-appointment reply).
6. **Frontend** — none (WhatsApp-side only), aside from the Settings-page Flow-card gating in step 4 above if it turns out ungated today.
7. **Frontend tests** — a `SettingsPage` test asserting the Flow-setup card shown matches `merchant.vertical`, if that gating is added.

**Definition of done**: simulate an inbound "hi" webhook for a restaurant merchant → greeting menu shows exactly Place order / Track order (+ FAQs if configured), never Book appointment, never Talk to us; same simulation against an appointment merchant → exactly Book appointment / Appointment status (+ FAQs), never Place order, never Talk to us. Simulate "track my appointment" for an appointment merchant with one prior booking → correct status reply.

---

## Phase M5 — Cleanup: retire the additive toggle, docs & diagrams

Closes the gap between "vertical exists and gates everything" and "the old opt-in toggle still exists, unused, as dead weight."

1. **Migration** — drop `Merchant.appointment_booking_enabled` (its only remaining reads are removed in step 2 below; drop the column in the same PR that removes the last read, not before, so there's no window where code reads a dropped column).
2. **Domain** — grep-confirm zero remaining reads of `appointment_booking_enabled` across `backend/src` and `frontend/src` before the column drop; remove the Settings-page toggle UI and its mutation hook (`vertical` has fully superseded it — there's no longer a "same merchant, both features" state to represent).
3. **Adapters** — none beyond the migration.
4. **API** — remove `appointment_booking_enabled` from the `PUT/GET onboarding/profile` and Settings schemas if it's serialized there.
5. **Backend tests** — remove/update any test that seeds or asserts on `appointment_booking_enabled`; full `pytest`/`ruff`/`mypy` pass.
6. **Frontend** — Settings page loses the toggle section; full `biome`/`typecheck` pass.
7. **Frontend tests** — `SettingsPage.test.tsx` updated to drop toggle assertions; full `vitest` pass.

Plus, not code but part of this phase's definition of done:
- `ARCHITECTURE.md` §1: add `vertical` to the `Merchant` entity list. §9c: redraw as two branches from the intent-menu decision node — restaurant (existing browse→cart→checkout) and appointment (browse services → pick a slot → confirm → status tracking) — with the "Talk to us" node removed from both, not just one. §9b (onboarding flow) gains the new vertical-choice step at the top, before "Connect Meta/WhatsApp."
- `IMPLEMENTATION_PLAN.md`: once M1–M5 are actually built, append a "Phase 10 — Multi-vertical support" entry in the same after-the-fact narrative style Phases 5–9 already use (deviations from this plan, what shipped, definition of done met) — this document is the *before* plan; that entry becomes the *after* record, same convention the repo already follows.
- A live-browser walkthrough of both verticals end-to-end (register → onboard → WhatsApp simulation → dashboard), matching this repo's established practice (every prior phase's Definition of done was verified live, not just by test suite) before calling the whole effort done.

**Definition of done (whole plan)**: two fresh merchants — one `restaurant`, one `appointment` — each complete their own onboarding wizard from scratch, land on a dashboard whose nav shows exactly one of Orders/Appointments and one of Catalog/Services, and each merchant's WhatsApp greeting menu offers only the options valid for their vertical with "Talk to us" gone from both. `appointment_booking_enabled` no longer exists anywhere in the codebase. `ARCHITECTURE.md`'s diagrams match what's actually built.

---

## Explicitly out of scope (per the original ask)

- More than these two verticals — enforced structurally by the `MerchantVertical` enum (Decision 6), not just documentation.
- Multi-provider/staff calendars — `StaffResource`/`Appointment.staff_id` stay schema-ready-but-unused, as they already are today; single-provider-per-merchant assumed throughout.
- Payment integration for appointments — the existing placeholder stays inert (Decision 3).
- Any admin ability to switch a merchant's vertical post-onboarding — enforced by `set_vertical`'s immutability guard (Phase M1) and the wizard's read-only step (Phase M2), not merely absent from the UI.

## Suggested execution order

M1 → M2 → M3 can move in that strict sequence (each is a small, low-risk layer on the last, and M2/M3 both depend on M1's column existing). M4 is the one phase that touches live-merchant-facing behavior for *every* existing merchant (removing "Talk to us" is unconditional) — do it only once M1–M3 are merged and the vertical backfill (M1) has been confirmed correct against real data, so no merchant momentarily has neither vertical's menu available. M5 is cleanup and can trail behind at any point once M4's gating fully replaces the old toggle's reads.
