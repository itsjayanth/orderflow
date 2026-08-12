# Feature Proposal: Inventory & Stock Management

Status: proposed, not yet scheduled in `IMPLEMENTATION_PLAN.md`. Not part of `docs/project-brief.txt` — this is new scope layered on top of the MVP, written to fit the patterns in `ARCHITECTURE.md` (hexagonal modules, tenant-scoped repositories, append-only event logs, the existing domain-event bus) rather than inventing a parallel architecture.

## Why

Today `MenuItem.is_available` is a manual on/off toggle a staff member flips by hand. There's no notion of *how much* of an ingredient is left, no automatic tie between "we sold 10 butter chicken" and "we used 2kg less chicken," and no way to know a stockout is coming before the kitchen runs out mid-shift. This feature adds that layer: track ingredient-level stock, deduct it automatically as orders come in, alert staff before they run dry, and use order history to suggest what to reorder.

## 1. Core entities

New module: `backend/src/inventory/{domain,adapters,api}`, same hexagonal shape as every other module.

- **`InventoryItem`** — a merchant-scoped stock-keeping unit (e.g. "Paneer", "Basmati Rice", "Cooking Oil"). Fields: `name`, `unit` (kg / l / pcs / etc.), `current_quantity` (derived, not directly mutated), `reorder_threshold`, `reorder_quantity`, `unit_cost` (optional).
- **`MenuItemIngredient`** — the recipe/BOM: links a `MenuItem` to the `InventoryItem`s and quantities it consumes per unit sold. This one join table is what makes both auto-deduction and trend-based planning possible — without it, "orders" and "stock" are two disconnected numbers.
- **`StockMovement`** — append-only ledger, same shape as the existing `PaymentEvent`/`OrderStatusEvent` audit trails. Fields: `movement_type` (`restock` / `sale_deduction` / `wastage` / `adjustment`), `quantity_delta`, `reference_order_id` (nullable), `recorded_by`, `occurred_at`. `InventoryItem.current_quantity` is a materialized view over this log, not a field anyone writes directly — gives a real audit trail and sidesteps race conditions on concurrent deductions.
- **`Supplier`** (lightweight, optional even within this feature) — name, contact, lead time, just enough to attach to a reorder suggestion later.

No new finite state machine is needed. Stock level is a derived number from an event log, not a multi-state object with illegal transitions to guard — consistent with the architecture's own rule of only introducing an explicit FSM where one is actually load-bearing.

## 2. Real-time restocking alerts

Reuses the domain-event bus already built for orders (`orders/domain/events.py` — worth promoting to `shared/events.py` once it's no longer order-only):

1. Inventory Service **subscribes** to `OrderPaid` / `OrderConfirmedCOD` (the same events Notification Service already consumes) → deducts stock per the `MenuItemIngredient` recipe → writes a `sale_deduction` `StockMovement`.
2. If a deduction crosses `reorder_threshold`, publish a new `LowStockDetected` event → Notification Service sends a WhatsApp/dashboard alert to staff (reuses the existing `NotificationChannel` port; just a new message kind, no new integration).
3. If an `InventoryItem` hits zero and is the sole ingredient gating a `MenuItem`, auto-toggle that item's `is_available = false` via Catalog Service — the same availability flag the dashboard already exposes, called cross-module the way Onboarding's `catalog_ready` gate already calls into Catalog today.

## 3. Order-trend-based stock planning

Pure read-side analytics — no new write path. Aggregate `OrderItem` quantities over rolling windows (7/14/30-day) per `MenuItem`, roll up through `MenuItemIngredient` to ingredient-level consumption, and surface "at this burn rate, X runs out in N days" plus a suggested reorder quantity. A simple moving average is enough for a first version — deliberately not real forecasting/ML. Fits the architecture's existing "dashboard reads are simple read-optimized queries" pattern; nothing here touches the write side.

## 4. Suggested phasing

Continues the numbering in `IMPLEMENTATION_PLAN.md` (Phases 1–8, all done):

- **Phase 9 — Inventory core**: `InventoryItem` CRUD, recipe/BOM linking UI, manual stock adjustment, dashboard Inventory page.
- **Phase 10 — Auto-deduction + alerts**: subscribe to order events, deduct per recipe, `LowStockDetected` → staff notification, auto out-of-stock toggle on the linked `MenuItem`.
- **Phase 11 — Trend-based restock suggestions**: consumption analytics, moving-average forecast, "Restock suggestions" dashboard view.

## 5. Explicitly out of scope (for this feature's own MVP)

- ML-based demand forecasting (moving average only, for now)
- Multi-outlet inventory pooling (single-outlet-per-merchant assumption holds, per `ARCHITECTURE.md`)
- Barcode scanning, batch/expiry tracking
- Automated purchase-order submission to suppliers (suggestions only, staff acts manually)

## 6. Open questions

- Does the pilot restaurant actually maintain ingredient-level recipes, or only track a few high-risk items (e.g. just the protein, not every garnish)? Affects how much BOM data entry Phase 9 asks staff to do up front.
- Should `wastage` / `adjustment` movements require a reason code for reporting, or free text is fine for MVP?
- Alert channel: WhatsApp to the same staff number used for order notifications, a dashboard banner, or both?
