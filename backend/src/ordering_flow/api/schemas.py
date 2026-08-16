import uuid
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator


class PublicMenuItemOut(BaseModel):
    menu_item_id: uuid.UUID
    category: str
    name: str
    price: Decimal
    image_url: str | None = None

    model_config = {"from_attributes": True}


class PublicMenuOut(BaseModel):
    business_name: str
    items: list[PublicMenuItemOut]
    # Null until the merchant has connected WhatsApp (onboarding) -- lets
    # the webview link back to the chat (e.g. after checkout) since a
    # website can't programmatically return the customer to WhatsApp itself.
    merchant_whatsapp_number: str | None = None


class OrderingFlowCheckoutItem(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int


class OrderingFlowDeliveryAddressIn(BaseModel):
    line1: str = Field(min_length=1, max_length=255)
    line2: str | None = None
    landmark: str | None = None
    city: str = Field(min_length=1, max_length=128)
    pincode: str = Field(min_length=1, max_length=16)

    @field_validator("line1", "city", "pincode")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class OrderingFlowCheckoutRequest(BaseModel):
    customer_whatsapp_number: str
    customer_display_name: str = Field(min_length=1, max_length=255)
    items: list[OrderingFlowCheckoutItem]
    payment_method: Literal["online", "cod"] = "online"
    order_type: Literal["pickup", "delivery"] = "pickup"
    # Raw address fields rather than a pre-created address id -- the public
    # webview has no prior address to reference, so checkout is the moment
    # the Address row gets created (see perform_checkout's
    # new_delivery_address param, which turns this into a delivery_address_id
    # on the Order once the Customer row exists).
    delivery_address: OrderingFlowDeliveryAddressIn | None = None
    # The alternate number to call for *this* order, or None when the
    # customer chose "use my WhatsApp number" -- passed straight through to
    # perform_checkout's contact_phone kwarg, which resolves None to
    # customer_whatsapp_number. Deliberately not validated as strictly as
    # customer_whatsapp_number: nobody looks a customer up by this number,
    # it's purely informational for whoever calls about the order.
    contact_phone: str | None = None

    @field_validator("customer_display_name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("customer_display_name must not be blank")
        return stripped

    @field_validator("contact_phone")
    @classmethod
    def _contact_phone_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("contact_phone must not be blank")
        return stripped

    @model_validator(mode="after")
    def _delivery_requires_address(self) -> Self:
        if self.order_type == "delivery" and self.delivery_address is None:
            raise ValueError("delivery_address is required when order_type is 'delivery'")
        return self


class OrderingFlowCheckoutResponse(BaseModel):
    order_id: uuid.UUID
    order_number: int
    payment_status: str
    fulfillment_status: str | None
    total: str
    payment_link_url: str | None


class OrderingFlowAddressOut(BaseModel):
    line1: str
    line2: str | None
    landmark: str | None
    city: str
    pincode: str

    model_config = {"from_attributes": True}


class OrderingFlowCustomerLookupOut(BaseModel):
    """Returned by GET /{merchant_id}/customer-lookup for a returning
    customer so the webview can prefill name + address without asking
    again -- only ever the merchant's own customer, matched on the exact
    (merchant_id, whatsapp_number) pair, same scoping as checkout's
    find_or_create."""

    display_name: str | None
    address: OrderingFlowAddressOut | None
    # The alternate contact number this customer previously chose (None if
    # they've always used "same as WhatsApp"), so the webview can
    # pre-select "Use a different number" and prefill the box for a
    # returning customer instead of asking again.
    default_contact_phone: str | None
