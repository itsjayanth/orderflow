from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from catalog.domain.models import Item
from customers.domain.models import Address
from ordering_flow.domain.checkout import CheckoutItem, NewDeliveryAddress


def build_category_screen_data(*, business_name: str, items: list[Item]) -> dict[str, Any]:
    """The CATEGORY screen's `data` on Flow INIT -- distinct categories in
    first-seen catalog order (not alphabetical, so a merchant's own
    ordering, e.g. Starters before Desserts, is preserved). A menu with
    only one category still gets a (trivial) category screen rather than
    special-casing straight to ITEMS -- one less branch to keep correct."""
    seen: list[str] = []
    for item in items:
        if item.is_available and item.category not in seen:
            seen.append(item.category)
    return {
        "business_name": business_name,
        "categories": [{"id": category, "title": category} for category in seen],
    }


def build_items_screen_data(*, category: str, items: list[Item]) -> dict[str, Any]:
    """The ITEMS screen's `data`, filtered to one category -- one
    CheckboxGroup option per available item in it. Flow JSON layouts are a
    static component tree, but a component's `data-source` array can be
    dynamic length, which is what lets this handle any category size
    without editing the Flow JSON. `image` is only included when a cached
    one exists (flows/api/router.py populates it on first use, see
    flows/domain/images.py) -- CheckboxGroup renders fine without it, so a
    slow/failed fetch for one item degrades gracefully rather than blocking
    the whole category."""
    options = []
    for item in items:
        if not (item.is_available and item.category == category):
            continue
        option: dict[str, Any] = {
            "id": str(item.item_id),
            "title": f"{item.name} - Rs {item.price}",
            "description": item.category,
        }
        if item.flow_image_base64:
            option["image"] = item.flow_image_base64
            option["alt-text"] = item.name
        options.append(option)
    return {"category_name": category, "menu_options": options}


class NoItemsSelectedError(Exception):
    """CheckboxGroup's `required: true` should block an empty submission
    client-side already -- this is a defensive fallback for the data
    already having reached the server some other way (a stale/replayed
    request), not the primary way empty carts get caught."""


@dataclass(frozen=True, slots=True)
class CartResolution:
    checkout_items: list[CheckoutItem]
    summary_text: str


def resolve_cart(*, selected_item_ids: list[str], items: list[Item]) -> CartResolution:
    """Matches the ids the customer checked (strings, since CheckboxGroup
    values always round-trip as strings) back against the live catalog --
    not against whatever the MENU screen was shown with, so a price change
    or an item going unavailable between screens is picked up here rather
    than trusted from client state."""
    by_id = {str(item.item_id): item for item in items}
    checkout_items: list[CheckoutItem] = []
    lines: list[str] = []
    total = Decimal("0")

    for raw_id in selected_item_ids:
        item = by_id.get(raw_id)
        if item is None or not item.is_available:
            continue
        checkout_items.append(CheckoutItem(item_id=item.item_id, quantity=1))
        lines.append(f"1x {item.name} - Rs {item.price}")
        total += item.price

    if not checkout_items:
        raise NoItemsSelectedError()

    summary = "\n".join(lines) + f"\n\nTotal: Rs {total}"
    return CartResolution(checkout_items=checkout_items, summary_text=summary)


def build_details_screen_data(
    *,
    cart_summary: str,
    saved_address: Address | None,
    saved_customer_name: str | None,
    saved_default_contact_phone: str | None,
) -> dict[str, Any]:
    """The DETAILS screen's `data` -- cart_summary for display, plus
    whatever a returning customer already told us (name, contact-number
    preference, saved address) so the Flow JSON's Form `init-values` can
    default to their last choice instead of asking again every order.
    Empty strings, not null, for anything that binds into a TextInput's
    initial value: a null there is more likely to render literally as the
    string "None" than as blank.

    saved_contact_choice/saved_contact_phone mirror
    Customer.default_contact_phone's own null-means-"same as WhatsApp"
    convention (see customers/domain/models.py): a customer who has never
    asked for a different number gets "same" (the RadioButtonsGroup's
    first, default-feeling option), not an empty/invalid choice id.
    has_saved_address is a "true"/"false" *string* (not a JSON bool) since
    Flow JSON `If` conditions compare against string literals -- see the
    condition on the address block below."""
    has_saved_address = saved_address is not None
    saved_address_display = ""
    if saved_address is not None:
        # The full sentence lives in this one value, not split between a
        # static JSON string and an interpolated field -- WhatsApp's Flow
        # client only reliably substitutes ${data.x} when it's the entire
        # field content, not embedded partway through a longer string (a
        # live test showed the literal text "${data.saved_address_display}"
        # rendered verbatim when the JSON tried "Your saved address: ${...}").
        saved_address_display = (
            f"Your saved address: {saved_address.line1}, "
            f"{saved_address.city} - {saved_address.pincode}"
        )
    return {
        "cart_summary": cart_summary,
        "saved_customer_name": saved_customer_name or "",
        "saved_contact_choice": "different" if saved_default_contact_phone else "same",
        "saved_contact_phone": saved_default_contact_phone or "",
        "has_saved_address": "true" if has_saved_address else "false",
        "saved_address_display": saved_address_display,
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
    customer_name: str | None
    contact_choice: str  # "same" | "different"
    contact_phone: str | None
    address_choice: str | None  # "same" | "new" | None (pickup, or no saved address to reuse)
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
        customer_name=(payload.get("customer_name") or "").strip() or None,
        contact_choice=(payload.get("contact_choice") or "").strip() or "same",
        contact_phone=(payload.get("contact_phone") or "").strip() or None,
        address_choice=(payload.get("address_choice") or "").strip() or None,
        address_line1=(payload.get("address_line1") or "").strip() or None,
        address_city=(payload.get("address_city") or "").strip() or None,
        address_pincode=(payload.get("address_pincode") or "").strip() or None,
        address_landmark=(payload.get("address_landmark") or "").strip() or None,
    )


def resolve_contact_phone(submission: FlowOrderSubmission) -> str | None:
    """Matches perform_checkout's `contact_phone` param semantics: None
    means "same as WhatsApp". Only trusts the typed-in number when the
    customer explicitly chose "different" -- a stray contact_phone value
    (e.g. still sitting in the Form's init-values from last order) should
    never override that choice just because the field has *something* in
    it."""
    if submission.contact_choice == "different":
        return submission.contact_phone
    return None


def build_new_delivery_address(submission: FlowOrderSubmission) -> NewDeliveryAddress | None:
    """Only relevant for a brand-new (or edited) address -- the caller is
    responsible for not calling this at all when the customer chose to
    reuse their saved address (submission.address_choice == "same"; see
    conversation/domain/handler.py). None both when the customer chose
    pickup, and when they chose delivery but left the address incomplete
    -- the Flow JSON doesn't block that client-side (no per-field
    conditional validation in v1, see flows/assets/order_flow.json), so
    checkout still proceeds as a delivery order with no address rather
    than failing outright; the merchant follows up by phone. A known v1
    gap, not silent data loss -- perform_checkout still records
    order_type="delivery" either way."""
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
