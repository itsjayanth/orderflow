from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from catalog.domain.models import MenuItem
from ordering_flow.domain.checkout import CheckoutItem, NewDeliveryAddress


def build_menu_screen_data(*, business_name: str, menu_items: list[MenuItem]) -> dict[str, Any]:
    """The MENU screen's `data` on Flow INIT -- one CheckboxGroup option per
    available item. Flow JSON layouts are static (a fixed component tree),
    but a component's `data-source` array can be dynamic length, which is
    what lets this handle any menu size without editing the Flow JSON."""
    return {
        "business_name": business_name,
        "menu_options": [
            {
                "id": str(item.menu_item_id),
                "title": f"{item.name} - Rs {item.price}",
                "description": item.category,
            }
            for item in menu_items
            if item.is_available
        ],
    }


class NoItemsSelectedError(Exception):
    """CheckboxGroup's `required: true` should block an empty submission
    client-side already -- this is a defensive fallback for the data
    already having reached the server some other way (a stale/replayed
    request), not the primary way empty carts get caught."""


@dataclass(frozen=True, slots=True)
class CartResolution:
    checkout_items: list[CheckoutItem]
    summary_text: str


def resolve_cart(*, selected_item_ids: list[str], menu_items: list[MenuItem]) -> CartResolution:
    """Matches the ids the customer checked (strings, since CheckboxGroup
    values always round-trip as strings) back against the live catalog --
    not against whatever the MENU screen was shown with, so a price change
    or an item going unavailable between screens is picked up here rather
    than trusted from client state."""
    by_id = {str(item.menu_item_id): item for item in menu_items}
    checkout_items: list[CheckoutItem] = []
    lines: list[str] = []
    total = Decimal("0")

    for raw_id in selected_item_ids:
        item = by_id.get(raw_id)
        if item is None or not item.is_available:
            continue
        checkout_items.append(CheckoutItem(menu_item_id=item.menu_item_id, quantity=1))
        lines.append(f"1x {item.name} - Rs {item.price}")
        total += item.price

    if not checkout_items:
        raise NoItemsSelectedError()

    summary = "\n".join(lines) + f"\n\nTotal: Rs {total}"
    return CartResolution(checkout_items=checkout_items, summary_text=summary)


@dataclass(frozen=True, slots=True)
class FlowOrderSubmission:
    selected_item_ids: list[str]
    order_type: str  # "pickup" | "delivery"
    payment_method: str  # "cod" | "online"
    address_line1: str | None
    address_city: str | None
    address_pincode: str | None
    address_landmark: str | None


def parse_flow_completion(payload: dict[str, Any]) -> FlowOrderSubmission:
    """Parses the `complete` action's payload, delivered by WhatsApp as a
    regular inbound message (interactive.nfm_reply.response_json) once the
    customer finishes the Flow -- see webhook_parser.py."""
    return FlowOrderSubmission(
        selected_item_ids=list(payload.get("selected_items") or []),
        order_type=payload.get("order_type") or "pickup",
        payment_method=payload.get("payment_method") or "cod",
        address_line1=(payload.get("address_line1") or "").strip() or None,
        address_city=(payload.get("address_city") or "").strip() or None,
        address_pincode=(payload.get("address_pincode") or "").strip() or None,
        address_landmark=(payload.get("address_landmark") or "").strip() or None,
    )


def build_new_delivery_address(submission: FlowOrderSubmission) -> NewDeliveryAddress | None:
    """None both when the customer chose pickup, and when they chose
    delivery but left the address incomplete -- the Flow JSON doesn't
    block that client-side (no per-field conditional validation in v1, see
    flows/assets/order_flow.json), so checkout still proceeds as a
    delivery order with no address rather than failing outright; the
    merchant follows up by phone. A known v1 gap, not silent data loss --
    perform_checkout still records order_type="delivery" either way."""
    if submission.order_type != "delivery":
        return None
    if not (submission.address_line1 and submission.address_city and submission.address_pincode):
        return None
    return NewDeliveryAddress(
        line1=submission.address_line1,
        city=submission.address_city,
        pincode=submission.address_pincode,
        landmark=submission.address_landmark,
    )
