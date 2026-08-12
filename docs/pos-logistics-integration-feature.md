# Feature Proposal: POS (Petpooja) & Logistics Partner Integration

Status: proposed, not yet scheduled in `IMPLEMENTATION_PLAN.md`. Continues after the Inventory & Stock Management proposal (`docs/inventory-stock-management-feature.md`, Phases 9–11) — this doc picks up at Phase 12. Two distinct integrations, covered together because both are "Order Service talks to an external system" seams that `ARCHITECTURE.md` already left room for.

## Why

- **Petpooja** is explicitly the planned Phase 2 in `docs/project-brief.txt` — MVP deliberately stops at "order appears in our app UI," and `Order`/`MenuItem` already carry nullable `external_pos_order_id` / `external_pos_item_id` seam fields for exactly this. This doc turns that seam into a real plan.
- **Logistics partner integration** (rider assignment, pickup/drop tracking, delivery status) is *not* in the brief. `ARCHITECTURE.md` §11 explicitly scoped `order_type`/`Address` as "data capture only... does not add rider assignment, delivery tracking, or route/logistics management" and flagged that adding real logistics is "a bigger scope conversation." This doc is that conversation — flagging it up front, same as the inventory doc flagged its own new-scope status.

## Part A — Petpooja (POS) integration

### 1. What already exists to build on
- `Order.external_pos_order_id`, `MenuItem.external_pos_item_id` (nullable, unused today).
- `OrderStatusEvent.changed_by` already accepts a system actor, not just a `staff_user_id` — a POS-driven status push is the same code path a staff tap uses.
- The domain-event bus (`OrderPaid`, `OrderConfirmedCOD`, etc.) that Notification Service already subscribes to.

### 2. New entities
- **`PetpoojaCredentials`** (1:1 with `Merchant`, same shape as `MerchantPaymentCredentials`/`WhatsAppBusinessAccount`): `restaurant_id`, `app_key`, `app_secret`, `access_token_encrypted`, `connection_status`. Settable from the dashboard Settings page, same pattern as Razorpay/WhatsApp credentials.
- **`PosSyncEvent`** (append-only, mirrors `PaymentEvent`): `order_id`, `direction` (`push` / `pull`), `event_type` (`order_pushed`, `push_failed`, `status_pulled`, `catalog_synced`), `raw_payload`, `occurred_at`. Gives a debuggable audit trail for what is otherwise an opaque third-party API call.

### 3. Flow
- **Outbound (our order → Petpooja)**: new `pos_sync` module subscribes to the same `OrderConfirmed`-class events Notification Service consumes → calls Petpooja's order-injection API → stores `external_pos_order_id`, writes a `PosSyncEvent`. Failure is logged and retried (bounded backoff), never blocks the order's own state machine — Petpooja push is a side effect, not a gate, exactly like Notification Service's existing "fire and forget, never block the triggering request" contract.
- **Inbound (Petpooja → our order)**: a webhook endpoint receives Petpooja's status pushes, resolves the order via `external_pos_order_id`, and calls Order Service's existing `fulfillment_status` transition function with `changed_by="system:petpooja"` — no new transition table, reuses Phase 4's state machine as-is.
- **Catalog sync (optional, second pass)**: pull categories/items from Petpooja periodically or on-demand, map to `MenuItem.external_pos_item_id`. Worth deferring — MVP dashboard catalog management already works standalone, and two-way catalog sync (ours vs. Petpooja's) is its own can of worms (conflict resolution, price drift) best scoped separately once outbound order sync is proven.

### 4. Explicitly out of scope (first pass)
- Two-way catalog sync (start with dashboard as source of truth, POS push only).
- KDS/kitchen-printer auto-ticketing (brief already excludes this).
- UrbanPiper or other POS providers (brief names Petpooja first, UrbanPiper "later").

## Part B — Logistics partner integration

### 1. New entities
- **`DeliveryAssignment`** — one per delivery order: `order_id` (FK), `provider` (e.g. the chosen aggregator), `provider_delivery_id`, `rider_name`/`rider_phone` (nullable until assigned), `status`, `tracking_url`, `requested_at`/`picked_up_at`/`delivered_at`.
- **`status`** needs a real transition table (unlike stock, this has genuine illegal transitions to guard): `requested → rider_assigned → picked_up → out_for_delivery → delivered`, plus `* → failed`/`cancelled`. Same "explicit FSM, unit-tested in isolation" pattern as `orders/domain/state_machine.py`.

### 2. New port
- **`DeliveryProvider`** protocol (Strategy pattern, same shape as `PaymentGateway`/`NotificationChannel`): `request_delivery(order)`, `cancel_delivery(assignment)`, `verify_webhook(payload, signature)`. One concrete adapter for whichever aggregator the pilot restaurants actually use (Porter/Shadowfax/Dunzo-style on-demand delivery API — needs picking before building, same "don't build blind against nothing real" lesson Phases 5–8 already learned with Razorpay/Meta).

### 3. Flow
- Order reaches `fulfillment_status = ready` **and** `order_type = delivery` → Order Service publishes a `DeliveryRequested`-class event → new Delivery Service creates the `DeliveryAssignment`, calls the provider adapter, stores `provider_delivery_id`.
- Provider webhook updates `DeliveryAssignment.status` → triggers a customer WhatsApp notification via the existing `NotificationChannel` port (new message kinds: "rider on the way," "delivered") and surfaces rider name/phone + tracking link on the order detail page in the dashboard.
- `delivered` can optionally auto-advance `Order.fulfillment_status → completed` instead of requiring a manual staff tap — worth a product decision, not an architecture one.

### 4. Explicitly out of scope (first pass)
- Route optimization / multi-drop batching.
- In-house rider fleet management (this assumes a third-party on-demand aggregator, not owned riders).
- Delivery fee calculation/passthrough to the customer (assume the aggregator's fee is a merchant cost for MVP, not itemized in the order total).

## Suggested phasing

Continues the numbering from the inventory proposal:

- **Phase 12 — Petpooja outbound push**: credentials settings UI, `pos_sync` module, order push on confirm events, `PosSyncEvent` log, dashboard visibility into sync status/failures.
- **Phase 13 — Petpooja inbound status sync**: webhook endpoint, maps to existing fulfillment transitions, `changed_by="system:petpooja"` visible in the existing order-status audit trail.
- **Phase 14 — Logistics partner integration**: pick one aggregator, `DeliveryProvider` adapter + `DeliveryAssignment` state machine, auto-request on `ready`, webhook-driven status + customer notifications, dashboard tracking view.

## Open questions

- Which logistics aggregator do the pilot Bangalore restaurants actually use today (if any)? Determines the first adapter to build — don't build one blind.
- Does `delivered` auto-complete the order, or does staff still confirm completion manually?
- Is the Petpooja catalog the source of truth once connected, or does our dashboard stay authoritative and only push? (Affects whether Phase 12 needs to reconcile pricing conflicts at all.)
- Delivery fee handling — merchant-absorbed cost, or itemized into the customer-facing total? Affects the `Order`/`OrderItem` model, not just this integration.
