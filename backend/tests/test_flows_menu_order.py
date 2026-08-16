import uuid
from decimal import Decimal

import pytest

from catalog.domain.models import MenuItem
from flows.domain.menu_order import (
    NoItemsSelectedError,
    build_menu_screen_data,
    build_new_delivery_address,
    parse_flow_completion,
    resolve_cart,
)


def _item(*, name: str, price: str, category: str = "Mains", is_available: bool = True) -> MenuItem:
    return MenuItem(
        menu_item_id=uuid.uuid4(),
        merchant_id=uuid.uuid4(),
        item_number=1,
        category=category,
        name=name,
        price=Decimal(price),
        is_available=is_available,
    )


def test_build_menu_screen_data_excludes_unavailable_items() -> None:
    available = _item(name="Butter Chicken", price="349.00")
    unavailable = _item(name="Sold Out Curry", price="199.00", is_available=False)

    data = build_menu_screen_data(business_name="Varkey's", menu_items=[available, unavailable])

    assert data["business_name"] == "Varkey's"
    titles = [opt["title"] for opt in data["menu_options"]]
    assert "Butter Chicken - Rs 349.00" in titles[0]
    assert len(data["menu_options"]) == 1


def test_resolve_cart_computes_total_and_summary() -> None:
    item1 = _item(name="Butter Chicken", price="349.00")
    item2 = _item(name="Naan", price="40.00")

    resolution = resolve_cart(
        selected_item_ids=[str(item1.menu_item_id), str(item2.menu_item_id)],
        menu_items=[item1, item2],
    )

    assert len(resolution.checkout_items) == 2
    assert "Total: Rs 389.00" in resolution.summary_text


def test_resolve_cart_ignores_stale_or_unavailable_ids() -> None:
    item = _item(name="Butter Chicken", price="349.00")
    stale_id = str(uuid.uuid4())
    unavailable = _item(name="Sold Out", price="99.00", is_available=False)

    resolution = resolve_cart(
        selected_item_ids=[str(item.menu_item_id), stale_id, str(unavailable.menu_item_id)],
        menu_items=[item, unavailable],
    )

    assert len(resolution.checkout_items) == 1
    assert resolution.checkout_items[0].menu_item_id == item.menu_item_id


def test_resolve_cart_raises_when_nothing_selected() -> None:
    item = _item(name="Butter Chicken", price="349.00")

    with pytest.raises(NoItemsSelectedError):
        resolve_cart(selected_item_ids=[], menu_items=[item])


def test_parse_flow_completion_defaults_and_blank_address_fields() -> None:
    submission = parse_flow_completion(
        {
            "selected_items": ["a", "b"],
            "order_type": "delivery",
            "payment_method": "online",
            "address_line1": "  ",
            "address_city": "Bengaluru",
        }
    )

    assert submission.selected_item_ids == ["a", "b"]
    assert submission.order_type == "delivery"
    assert submission.payment_method == "online"
    assert submission.address_line1 is None  # blank/whitespace-only collapses to None
    assert submission.address_city == "Bengaluru"
    assert submission.address_pincode is None


def test_parse_flow_completion_defaults_when_fields_missing() -> None:
    submission = parse_flow_completion({})

    assert submission.selected_item_ids == []
    assert submission.order_type == "pickup"
    assert submission.payment_method == "cod"


def test_build_new_delivery_address_none_for_pickup() -> None:
    submission = parse_flow_completion({"order_type": "pickup"})

    assert build_new_delivery_address(submission) is None


def test_build_new_delivery_address_none_when_incomplete() -> None:
    submission = parse_flow_completion({"order_type": "delivery", "address_line1": "12 MG Road"})

    assert build_new_delivery_address(submission) is None


def test_build_new_delivery_address_when_complete() -> None:
    submission = parse_flow_completion(
        {
            "order_type": "delivery",
            "address_line1": "12 MG Road",
            "address_city": "Bengaluru",
            "address_pincode": "560001",
            "address_landmark": "Near metro",
        }
    )

    address = build_new_delivery_address(submission)

    assert address is not None
    assert address.line1 == "12 MG Road"
    assert address.city == "Bengaluru"
    assert address.pincode == "560001"
    assert address.landmark == "Near metro"
