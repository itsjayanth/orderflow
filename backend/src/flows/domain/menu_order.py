from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from catalog.domain.models import MenuItem
from customers.domain.models import Address
from ordering_flow.domain.checkout import CheckoutItem, NewDeliveryAddress


def build_category_screen_data(*, business_name: str, menu_items: list[MenuItem]) -> dict[str, Any]:
    """The CATEGORY screen's `data` on Flow INIT -- distinct categories in
    first-seen catalog order (not alphabetical, so a merchant's own
    ordering, e.g. Starters before Desserts, is preserved). A menu with
    only one category still gets a (trivial) category screen rather than
    special-casing straight to ITEMS -- one less branch to keep correct."""
    seen: list[str] = []
    for item in menu_items:
        if item.is_available and item.category not in seen:
            seen.append(item.category)
    return {
        "business_name": business_name,
        "categories": [{"id": category, "title": category} for category in seen],
    }


def build_items_screen_data(*, category: str, menu_items: list[MenuItem]) -> dict[str, Any]:
    """The ITEMS screen's `data`, filtered to one category -- one
    CheckboxGroup option per available item in it. Flow JSON layouts are a
    static component tree, but a component's `data-source` array can be
    dynamic length, which is what lets this handle any category size
    without editing the Flow JSON."""
    return {
        "category_name": category,
        "menu_options": [
            {
                "id": str(item.menu_item_id),
                "title": f"{item.name} - Rs {item.price}",
                "description": item.category,
            }
            for item in menu_items
            if item.is_available and item.category == category
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


def build_details_screen_data(
    *, cart_summary: str, saved_address: Address | None
) -> dict[str, Any]:
    """The DETAILS screen's `data` -- cart_summary for display, plus a
    returning customer's saved address (if any) so the Flow JSON's Form
    `init-values` can prefill it instead of asking again every order.
    Empty strings, not null, for the address fields: init-values binds
    them directly into TextInput initial values, and a null there is more
    likely to render literally as the string "None" than as blank."""
    return {
        "cart_summary": cart_summary,
        "saved_address_line1": saved_address.line1 if saved_address else "",
        "saved_address_city": saved_address.city if saved_address else "",
        "saved_address_pincode": saved_address.pincode if saved_address else "",
        "saved_address_landmark": (saved_address.landmark or "") if saved_address else "",
    }


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
