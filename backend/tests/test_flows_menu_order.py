import uuid
from decimal import Decimal

import pytest

from catalog.domain.models import Item
from customers.domain.models import Address
from flows.domain.menu_order import (
    NoItemsSelectedError,
    build_category_screen_data,
    build_details_screen_data,
    build_items_screen_data,
    build_new_delivery_address,
    parse_flow_completion,
    resolve_cart,
    resolve_contact_phone,
)


def _item(
    *, name: str, price: str, category: str = "Mains", is_available: bool = True
) -> Item:
    return Item(
        item_id=uuid.uuid4(),
        merchant_id=uuid.uuid4(),
        item_number=1,
        category=category,
        name=name,
        price=Decimal(price),
        is_available=is_available,
    )


def test_build_category_screen_data_returns_distinct_categories_in_first_seen_order() -> None:
    items = [
        _item(name="Naan", price="40.00", category="Breads"),
        _item(name="Butter Chicken", price="349.00", category="Mains"),
        _item(name="Roti", price="30.00", category="Breads"),
    ]

    data = build_category_screen_data(business_name="Varkey's", items=items)

    assert data["business_name"] == "Varkey's"
    assert data["categories"] == [
        {"id": "Breads", "title": "Breads"},
        {"id": "Mains", "title": "Mains"},
    ]


def test_build_category_screen_data_excludes_unavailable_items_categories() -> None:
    only_unavailable = _item(name="Sold Out", price="99.00", category="Soups", is_available=False)

    data = build_category_screen_data(business_name="Varkey's", items=[only_unavailable])

    assert data["categories"] == []


def test_build_items_screen_data_filters_to_one_category() -> None:
    mains_item = _item(name="Butter Chicken", price="349.00", category="Mains")
    bread_item = _item(name="Naan", price="40.00", category="Breads")

    data = build_items_screen_data(category="Mains", items=[mains_item, bread_item])

    assert data["category_name"] == "Mains"
    assert len(data["menu_options"]) == 1
    assert "Butter Chicken" in data["menu_options"][0]["title"]


def test_build_items_screen_data_excludes_unavailable_items() -> None:
    available = _item(name="Butter Chicken", price="349.00", category="Mains")
    unavailable = _item(name="Sold Out", price="99.00", category="Mains", is_available=False)

    data = build_items_screen_data(category="Mains", items=[available, unavailable])

    assert len(data["menu_options"]) == 1


def test_resolve_cart_computes_total_and_summary() -> None:
    item1 = _item(name="Butter Chicken", price="349.00")
    item2 = _item(name="Naan", price="40.00")

    resolution = resolve_cart(
        selected_item_ids=[str(item1.item_id), str(item2.item_id)],
        items=[item1, item2],
    )

    assert len(resolution.checkout_items) == 2
    assert "Total: Rs 389.00" in resolution.summary_text


def test_resolve_cart_ignores_stale_or_unavailable_ids() -> None:
    item = _item(name="Butter Chicken", price="349.00")
    stale_id = str(uuid.uuid4())
    unavailable = _item(name="Sold Out", price="99.00", is_available=False)

    resolution = resolve_cart(
        selected_item_ids=[str(item.item_id), stale_id, str(unavailable.item_id)],
        items=[item, unavailable],
    )

    assert len(resolution.checkout_items) == 1
    assert resolution.checkout_items[0].item_id == item.item_id


def test_resolve_cart_raises_when_nothing_selected() -> None:
    item = _item(name="Butter Chicken", price="349.00")

    with pytest.raises(NoItemsSelectedError):
        resolve_cart(selected_item_ids=[], items=[item])


def test_build_details_screen_data_blank_when_no_saved_address() -> None:
    data = build_details_screen_data(
        cart_summary="1x Naan - Rs 40.00",
        saved_address=None,
        saved_customer_name=None,
        saved_default_contact_phone=None,
    )

    assert data["cart_summary"] == "1x Naan - Rs 40.00"
    assert data["saved_customer_name"] == ""
    assert data["saved_contact_choice"] == "same"
    assert data["saved_contact_phone"] == ""
    assert data["has_saved_address"] == "false"
    assert data["saved_address_display"] == ""
    assert data["saved_address_line1"] == ""
    assert data["saved_address_city"] == ""
    assert data["saved_address_pincode"] == ""
    assert data["saved_address_landmark"] == ""


def test_build_details_screen_data_prefills_from_saved_address() -> None:
    address = Address(
        address_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        merchant_id=uuid.uuid4(),
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
        landmark="Near metro",
    )

    data = build_details_screen_data(
        cart_summary="1x Naan - Rs 40.00",
        saved_address=address,
        saved_customer_name="Asha",
        saved_default_contact_phone=None,
    )

    assert data["has_saved_address"] == "true"
    assert data["saved_address_display"] == "Your saved address: 12 MG Road, Bengaluru - 560001"
    assert data["saved_address_line1"] == "12 MG Road"
    assert data["saved_address_city"] == "Bengaluru"
    assert data["saved_address_pincode"] == "560001"
    assert data["saved_address_landmark"] == "Near metro"
    assert data["saved_customer_name"] == "Asha"
    assert data["saved_contact_choice"] == "same"


def test_build_details_screen_data_landmark_blank_not_none() -> None:
    address = Address(
        address_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        merchant_id=uuid.uuid4(),
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
        landmark=None,
    )

    data = build_details_screen_data(
        cart_summary="",
        saved_address=address,
        saved_customer_name=None,
        saved_default_contact_phone=None,
    )

    assert data["saved_address_landmark"] == ""


def test_build_details_screen_data_contact_choice_different_when_saved_number_set() -> None:
    data = build_details_screen_data(
        cart_summary="",
        saved_address=None,
        saved_customer_name=None,
        saved_default_contact_phone="919999999999",
    )

    assert data["saved_contact_choice"] == "different"
    assert data["saved_contact_phone"] == "919999999999"


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
    assert submission.customer_name is None
    assert submission.contact_choice == "same"
    assert submission.contact_phone is None
    assert submission.address_choice is None


def test_parse_flow_completion_parses_name_contact_and_address_choice() -> None:
    submission = parse_flow_completion(
        {
            "selected_items": ["a"],
            "order_type": "delivery",
            "payment_method": "cod",
            "customer_name": "Asha",
            "contact_choice": "different",
            "contact_phone": "919999999999",
            "address_choice": "same",
        }
    )

    assert submission.customer_name == "Asha"
    assert submission.contact_choice == "different"
    assert submission.contact_phone == "919999999999"
    assert submission.address_choice == "same"


def test_parse_flow_completion_blank_contact_choice_defaults_to_same() -> None:
    submission = parse_flow_completion({"contact_choice": "  "})

    assert submission.contact_choice == "same"


def test_resolve_contact_phone_none_when_same_as_whatsapp() -> None:
    submission = parse_flow_completion({"contact_choice": "same", "contact_phone": "919999999999"})

    assert resolve_contact_phone(submission) is None


def test_resolve_contact_phone_returns_typed_number_when_different() -> None:
    submission = parse_flow_completion(
        {"contact_choice": "different", "contact_phone": "919999999999"}
    )

    assert resolve_contact_phone(submission) == "919999999999"


def test_resolve_contact_phone_none_when_different_but_left_blank() -> None:
    submission = parse_flow_completion({"contact_choice": "different"})

    assert resolve_contact_phone(submission) is None


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
