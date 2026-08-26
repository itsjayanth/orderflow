# Generic Platform Migration — Phase 0 Audit

Goal: turn Orderflow from a restaurant-only app into a vertical-agnostic
WhatsApp commerce platform. This document is the Phase 0 inventory required
by the task before any code changes: every restaurant/food-coupled term in
the repo, grouped by area, plus the real-data finding that determines
whether renames can be straight Alembic renames or need an additive/
backfill/deprecate path.

Terms searched (case-insensitive): `menu`, `dish`, `kitchen`, `cuisine`,
`fssai`, `chef`, `cook`/`cooking`, `restaurant`, `food`, `ingredient`.
~612 raw grep hits across `backend/src`, `frontend/src`, `docs`,
`backend/alembic`. Most are mechanical (identifier names, docstrings,
test fixture strings); the inventory below groups them by the concern
they represent, not a line-by-line dump.

## Real-data finding (blocks Phase 1–2 approach)

**Finding: yes, real (non-sandbox-throwaway) data exists.**

- `backend/demo_data_existing.sql` targets merchant_id
  `ede3aa6d-c111-47e2-bb75-65fbb915c5f1` — a real UUID (not the placeholder
  `11111111-...` used by `demo_data_varkeys.sql`'s from-scratch seed). Its
  header ("Demo data for **existing** Varkeys merchant") and its
  clean-up step ("keep merchant and staff") confirm this script is meant
  to run against a live database row that already exists — i.e. the
  sandbox merchant "Varkey's" wired to the live Meta WhatsApp Flow
  (IMPLEMENTATION_PLAN.md Phase 9) is a real row in a real deployed
  Postgres instance, not just a fixture.
- There is no evidence of *production scale* data (no backup dumps, no
  multi-tenant seed beyond this one merchant), but "one real row is still
  real data" — the standard here is "would a straight rename destroy
  something," not "is it a lot of data."
- `render.yaml`'s `preDeployCommand: alembic upgrade head` runs migrations
  immediately before the new backend image takes traffic (single service,
  no blue-green). There is no separate consumer of the old schema running
  concurrently with the new code.

**Chosen approach: straight Alembic renames (`op.rename_table`,
`alter_column(new_column_name=...)`), not additive-then-swap.**

Reasoning: a `RENAME` (table or column) is not a destructive drop — it
preserves every existing row and its data, it just changes the identifier
Postgres and SQLAlchemy address it by. Since the new backend code and the
migration deploy together (`preDeployCommand` gates traffic cutover), there
is no window where old code queries a renamed column. An additive
(add-new-column → backfill → dual-write → drop-old) path is the right tool
for zero-downtime migrations across independently-deployed services; this
app is a single Render web service with a pre-deploy migration gate, so
that complexity buys nothing here and would leave dead duplicate columns
behind. **Only true drops (removing a column/table outright with no
replacement) are treated as destructive and flagged for explicit
confirmation before running** — none are needed for this task; every
rename below has a direct 1:1 replacement.

## 1. Data model / DB schema

| File | Symbol | Rename |
|---|---|---|
| `backend/src/catalog/domain/models.py` | `MenuItem` class, `menu_items` table, `menu_item_id` PK | `Item`, `items`, `item_id` |
| `backend/src/catalog/domain/models.py` | `MerchantMenuItemCounter`, `merchant_menu_item_counters` table | `MerchantItemCounter`, `merchant_item_counters` |
| `backend/src/identity/domain/models.py` | `kitchen_address_line1/2`, `kitchen_city`, `kitchen_pincode` | `business_address_line1/2`, `business_city`, `business_pincode` |
| `backend/src/identity/domain/models.py` | `cuisine_type` | `business_category` |
| `backend/src/identity/domain/models.py` | `fssai_license_no` | `license_no` |
| `backend/src/orders/domain/models.py` | `OrderItem.menu_item_id` FK → `menu_items.menu_item_id` | `item_id` FK → `items.item_id` |
| `backend/src/customers/domain/models.py` | comment mentioning "menu items" | wording only |
| `backend/src/orders/domain/models.py` | comments mentioning "kitchen workflow" / "dashboard/kitchen" | wording only |

Migrations touching these columns/tables (history — left as-is, new
migration added on top): `08c207f9f086` (kitchen details),
`510663d692cb` / `6b4eed341b93` (image cols on `menu_items`),
`631b405088f1` (orders/order_items/order_status referencing
`menu_item_id`), `badd83266c3c`, `d0bb34e641c6` (`merchant_menu_item_counters`),
`e548a34798dc` (`menu_items` creation).

## 2. API schemas / request-response contracts

| File | Symbol | Rename |
|---|---|---|
| `backend/src/catalog/api/schemas.py` | `MenuItemOut`, `MenuItemCreate`, `MenuItemUpdate`, `menu_item_id` field | `ItemOut`, `ItemCreate`, `ItemUpdate`, `item_id` |
| `backend/src/onboarding/api/schemas.py` | `KitchenProfileOut`, `KitchenProfileUpdate`, `cuisine_type`, `fssai_license_no` fields | `BusinessProfileOut`, `BusinessProfileUpdate`, `business_category`, `license_no` |
| `backend/src/onboarding/api/schemas.py` | `OnboardingStatusOut.has_available_menu_item` | `has_available_item` |
| `backend/src/ordering_flow/api/schemas.py` | references to menu items in cart/checkout payloads | field renames to match Item |
| `backend/src/orders/api/schemas.py` | `menu_item_id` in order item payloads | `item_id` |
| `backend/src/payments/api/schemas.py` | incidental "menu"/"food" wording in examples/docstrings | wording only |

## 3. Domain & business logic (state machines, gating rules)

| File | Concern |
|---|---|
| `backend/src/conversation/domain/handler.py`, `intents.py` | "Talk to restaurant" copy, menu-item lookups in intent handling |
| `backend/src/flows/domain/menu_order.py` | WhatsApp Flow screen builders keyed to `menu_options`/menu item shape — see §4 |
| `backend/src/flows/domain/images.py` | menu item image handling — naming only, logic is generic |
| `backend/src/onboarding/domain/onboarding_service.py` | `catalog_ready` gate comments say "menu item"; **logic itself already checks "at least one available item exists" — vertical-agnostic, wording-only fix** |
| `backend/src/ordering_flow/domain/checkout.py` | cart/checkout logic reading catalog items — naming only, no food-specific branching found |
| `backend/src/orders/domain/state_machine.py`, `events.py` | `"Preparing"` fulfillment-status label (see §Phase 3) |

No `if business_type == "restaurant"` (or `cuisine_type` gating,
`fssai`-gating, etc.) branching was found anywhere in domain logic —
confirms the current code is already accidentally vertical-agnostic in
behavior; the coupling is naming/copy only, matching the task's design
principle.

## 4. WhatsApp Flow assets + conversation copy

- `backend/src/flows/assets/order_flow.json`: `menu_options` key (and
  nested screen refs to it) is food-shaped; `__example__` sample payloads
  use only food items.
- `backend/src/flows/domain/menu_order.py`: builder functions
  (`build_category_screen_data`, `build_items_screen_data`, etc.) read/
  write those same JSON keys — **must change in lockstep with the JSON**,
  and existing onboarded merchants (i.e. Varkey's) need the flow
  re-pushed via `POST /api/v1/onboarding/whatsapp/flow-sync` after
  deploy, since Meta caches the published Flow JSON independently of
  this repo.
- `backend/src/flows/api/router.py`: passes data through, naming only.
- `backend/src/conversation/domain/intents.py`,
  `backend/src/conversation/domain/handler.py`: "Talk to restaurant" →
  "Talk to us" / "Contact business"; greeting template is already generic
  (`Hi! Welcome to {merchant.business_name}.`) — no change needed there.

## 5. Frontend UI copy

Highest-signal files (full list of 33 matched files is mechanical —
mostly `menuItem`/`useMenuItems` identifier renames following §1–2):

- `frontend/src/features/catalog/CatalogPage.tsx` — "Menu & catalog
  control" heading, "Mains"/"Butter Chicken" placeholder examples.
- `frontend/src/features/catalog/useMenuItems.ts`,
  `useCreateMenuItem.ts`, `useUpdateMenuItem.ts` — hook/query-key renames
  to `useItems`, `useCreateItem`, `useUpdateItem`.
- `frontend/src/features/marketing/HomePage.tsx` — UtensilsCrossed icon,
  "kitchen setup", "your restaurant's data", "POS or kitchen setup".
- `frontend/src/features/marketing/components/ChatMockup.tsx`,
  `DashboardPreview.tsx` — mock content likely uses food examples.
- `frontend/src/features/onboarding/OnboardingPage.tsx`,
  `useOnboarding.ts` — "Kitchen details" step, `cuisine_type`/
  `fssai_license_no` form fields.
- `frontend/src/features/orders/*` (`StatusBadge.tsx`,
  `statusTransitions.ts`, `OrdersPage.tsx`, `StatusActionsMenu.tsx`) —
  "Preparing" status label (§Phase 3).
- `frontend/src/shared/api/types.ts`, `frontend/src/shared/lib/itemNumber.ts`
  — generated/shared types mirroring backend renames.
- `frontend/src/features/dashboard/DashboardHomePage.tsx` — likely
  "Preparing" stat tile label.

## 6. Docs

- `docs/project-brief.txt` — "non-restaurant verticals" listed as
  explicitly out of scope; needs updating since this task *is* that.
- `ARCHITECTURE.md` — titled around "WhatsApp Order-to-Kitchen MVP";
  entity docs for `Merchant`/`MenuItem` need to match §1–2 renames.
- `CLAUDE.md` — "Order flow — how it actually works today" section
  narrates `MenuItem`, kitchen fields, "Preparing" in prose; needs a
  pass once code changes land (kept accurate to code, not aspirational).
- `IMPLEMENTATION_PLAN.md` — phase write-ups reference `menu_items`,
  kitchen details, cuisine/FSSAI fields as historical implementation
  narrative; update to match renames, and flag Petpooja/POS-KDS
  integration as restaurant-vertical-specific rather than a universal
  Phase 2 assumption.

## 7. Tests & fixtures / seed data

- `backend/tests/test_catalog.py`, `test_flows_menu_order.py`,
  `test_ordering_flow.py`, `test_orders.py`, `test_order_state_machine.py`,
  `test_onboarding_flow.py`, `test_onboarding_whatsapp.py`,
  `test_conversation_handler.py`, `test_conversation_webhook_endpoint.py`,
  `test_notifications.py`, `test_notification_templates.py`,
  `test_scheduler.py`, `test_flows_encryption.py`, `test_flows_router.py`,
  `test_identity.py`, `test_customers.py`, `test_payments.py` — all
  reference `MenuItem`/`menu_item_id`/kitchen fields/`"Preparing"`
  fixtures or `business_name="Test Kitchen"`-style literals; need
  updating alongside their respective domain renames.
- `frontend/src/features/**/*.test.tsx` (Catalog, Orders, Onboarding,
  Dashboard, Ordering pages) — same, on the frontend side.
- `backend/demo_data_varkeys.sql`, `backend/demo_data_existing.sql`,
  `backend/DEMO_DATA.md` — food-only demo seed scripts; **must be
  updated for renamed columns/tables** (Phase 7) regardless of vertical
  additions, or they'll break against the new schema. Phase 7 adds a
  second, non-food demo dataset (e.g. a clothing store) alongside these,
  not a replacement.
- No `MenuItemRepository` class exists (the repository is already named
  generically per-module — `catalog/adapters/repository.py` exposes
  functions, not a `MenuItem`-prefixed class) — confirmed by reading the
  file; the task description's example name doesn't match current code,
  noting this so the phase isn't blocked looking for a symbol that
  doesn't exist under that name.

## Naming decision: `Item` vs `Product`

**Chosen: `Item`.** Reasoning:
- Matches the task's catalog description ("a flat (category, item, price,
  availability) model") and Phase 1's explicit `MenuItem` → `Item`
  instruction as the first-listed option.
- `has_available_item`, `item_id`, `item_options` read naturally across
  verticals (a shirt, a spark plug, a strip of tablets are all "items").
  "Product" skews retail-specific in a way that reads slightly oddly for
  a restaurant ("food product") or a pharmacy ("medicine product").
- Keeps the existing `item_number`/`itemNumber.ts` naming (already
  present in the frontend, per §5) consistent instead of introducing a
  second noun for the same concept.

Applied consistently: `Item` (model/table), `ItemOut/Create/Update`
(schemas), `item_id` (PK/FK), `useItems`/`useCreateItem`/`useUpdateItem`
(frontend hooks), `item_options` (WhatsApp Flow JSON key).

## Migration plan summary

All migrations below are additive/rename-only (no drops), consistent with
the real-data finding above:

1. `items` — rename `menu_items` table, `menu_item_id` → `item_id` column
   (and dependent FK on `order_items.menu_item_id` → `item_id`), rename
   `merchant_menu_item_counters` → `merchant_item_counters`.
2. `merchants` — rename `kitchen_address_line1/2` → `business_address_line1/2`,
   `kitchen_city` → `business_city`, `kitchen_pincode` → `business_pincode`,
   `cuisine_type` → `business_category`, `fssai_license_no` → `license_no`.

SQLAlchemy model changes and Alembic migrations must be committed
together per phase so `alembic upgrade head` and the ORM models never
disagree mid-commit.

---

## Completion summary (Phases 1–7)

All phases landed on `claude/orderflow-vertical-agnostic-g3g9tm`, one
commit (or a small cluster) per phase, backend (`pytest`/`ruff`/`mypy`)
and frontend (`tsc`/`biome`/`vitest`) green after every commit. Final
state: 391 backend tests passing (389 baseline + 2 new non-food-vertical
regression tests), 85 frontend tests passing (84 baseline + 1 new).

### Renames, table by table

| Area | Old | New |
|---|---|---|
| DB table | `menu_items` | `items` |
| DB table | `merchant_menu_item_counters` | `merchant_item_counters` |
| DB column | `items.menu_item_id` (PK) | `items.item_id` |
| DB column | `order_items.menu_item_id` (FK) | `order_items.item_id` |
| DB column | `merchants.kitchen_address_line1/2` | `merchants.business_address_line1/2` |
| DB column | `merchants.kitchen_city` | `merchants.business_city` |
| DB column | `merchants.kitchen_pincode` | `merchants.business_pincode` |
| DB column | `merchants.cuisine_type` | `merchants.business_category` |
| DB column | `merchants.fssai_license_no` | `merchants.license_no` |
| DB data | `orders.fulfillment_status = 'preparing'` | `'processing'` |
| DB data | `order_status_events.from_status/to_status = 'preparing'` | `'processing'` |
| DB data | `notification_templates.notification_kind = 'order_preparing'` | `'order_processing'` |
| Python model | `catalog.domain.models.MenuItem` | `Item` |
| Python model | `catalog.domain.models.MerchantMenuItemCounter` | `MerchantItemCounter` |
| Python schema | `catalog.api.schemas.MenuItemOut/Create/Update` | `ItemOut/Create/Update` |
| Python schema | `onboarding.api.schemas.KitchenProfileOut/Update` | `BusinessProfileOut/Update` |
| Python schema | `OnboardingStatusOut.has_available_menu_item` | `has_available_item` |
| Python schema | `OrderSummary.preparing_orders` | `processing_orders` |
| Python event | `orders.domain.events.OrderPreparing` | `OrderProcessing` |
| Python file | `flows/domain/menu_order.py` | `flows/domain/order_builder.py` |
| WhatsApp Flow JSON | `menu_options` key | `item_options` |
| Conversation copy | "Talk to restaurant" | "Talk to us" |
| Frontend hooks | `useMenuItems/useCreateMenuItem/useUpdateMenuItem` | `useItems/useCreateItem/useUpdateItem` |
| Frontend copy | onboarding step "Kitchen details" | "Business details" |
| Frontend field | "Cuisine type" free-text input | `business_category` select (Restaurant / Retail / Clothing / Auto Parts / Pharmacy / Other) |
| Frontend copy | dashboard "Preparing" stat/status | "Processing" |
| Frontend copy | "Menu & catalog control" heading | "Catalog control" |
| Demo data | `demo_data_varkeys.sql`, `demo_data_existing.sql` | fixed to match renamed schema (were broken by the DB renames above until this pass) |
| Demo data | — | added `demo_data_clothing_store.sql` (new, non-food vertical) |

### Migrations added

`b14b80115eb8` (menu_items→items rename), `9169aa688d5e` (stale
index/constraint names left over from that rename), `74f76cb509a0`
(merchant business-profile field renames), `70e512b414d0` (preparing→
processing data migration, including `order_status_events` and
`notification_templates`). All are straight renames/data updates, no
drops, consistent with the Phase 0 real-data finding.

### Manual follow-up required (cannot be automated from this repo)

1. **WhatsApp Flow re-sync for onboarded merchants.** The real sandbox
   merchant "Varkey's" (`merchant_id ede3aa6d-c111-47e2-bb75-65fbb915c5f1`)
   already has a Flow published to Meta under the old `menu_options`
   schema key. Meta caches the published Flow JSON independently of this
   repo, so after this deploys, call
   `POST /api/v1/onboarding/whatsapp/flow-sync` for that merchant (and
   any other already-onboarded merchant) to push the renamed
   `item_options` schema live. Until that runs, their live WhatsApp
   ordering Flow keeps using the old key name (harmless — Meta doesn't
   care what the key is called — but it means the deployed Flow and this
   repo's JSON are out of sync until re-synced).
2. **`docs/inventory-stock-management-feature.md` and
   `docs/pos-logistics-integration-feature.md`** (separate feature-
   proposal docs, out of this migration's scope per Phase 6) still
   reference `MenuItem` — worth a pass next time either doc is revisited,
   not urgent since they're proposals, not implemented code.
3. **Demo data is dev-only.** `demo_data_varkeys.sql`/
   `demo_data_existing.sql`/`demo_data_clothing_store.sql` are meant to
   run against a local dev database (`psql -h localhost`). Don't run
   them against a real deployed database without adjusting the merchant
   IDs — `demo_data_existing.sql` in particular targets a specific real
   merchant_id and will silently no-op the `UPDATE merchants` step (0
   rows) if that merchant doesn't exist in the target database, then
   fail on the `items` insert's FK constraint.
