import datetime
import uuid

from sqlalchemy import Boolean, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db import Base


class MerchantCustomerCounter(Base):
    """One row per merchant, tracking the next customer_number to hand out
    -- same pattern as orders/domain/models.py's MerchantOrderCounter and
    catalog/domain/models.py's MerchantItemCounter (see either for why
    a dedicated counter table beats MAX()+1 or a Postgres SEQUENCE here)."""

    __tablename__ = "merchant_customer_counters"

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("merchants.merchant_id"), primary_key=True
    )
    next_customer_number: Mapped[int] = mapped_column(default=1)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("merchant_id", "whatsapp_number", name="uq_customers_merchant_whatsapp"),
        UniqueConstraint("merchant_id", "customer_number", name="uq_customers_merchant_number"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    # Human-facing sequential reference (per merchant, starts at 1, never
    # reused/reset) -- same role order_number/item_number play for orders
    # and items. Shown in the dashboard, orders, and customers UI, and
    # usable as a search filter, instead of the raw customer_id UUID.
    customer_number: Mapped[int] = mapped_column()
    whatsapp_number: Mapped[str] = mapped_column(String(32))
    display_name: Mapped[str | None] = mapped_column(String(255), default=None)
    # Null means "call me on my WhatsApp number" (the common case) -- only
    # set when the customer has explicitly asked for a *different* number
    # to be used for delivery calls. Remembered across orders so that
    # choice doesn't need to be made every time; ordering_flow.domain.
    # checkout.perform_checkout is the only writer.
    default_contact_phone: Mapped[str | None] = mapped_column(String(32), default=None)
    # Historically dashboard-only ("never collected over WhatsApp") --
    # since the appointment-booking Flow now legitimately collects an
    # email from the customer themselves (see appointment_flow/domain/
    # booking.py and flows/domain/appointment_booking.py), this can also
    # be set from that flow's own submission, not just from staff.
    email: Mapped[str | None] = mapped_column(String(255), default=None)
    # 'cod' | 'online' | None -- the payment method chosen on this
    # customer's most recent order, remembered so checkout can prefill it
    # next time instead of defaulting to "online" for everyone. Same
    # "only a hint, never authoritative" role default_contact_phone plays:
    # nothing downstream trusts this for anything but a form default.
    # None for a customer who has never completed an order (or predates
    # this column).
    last_payment_method: Mapped[str | None] = mapped_column(String(16), default=None)
    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
    last_order_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
    # Soft-delete flag for the dashboard's Customers CRUD (deactivate, not
    # a hard DELETE) -- orders.customer_id FK's every past order to this
    # row, so removing it outright would either violate that FK or destroy
    # order history. Deactivated customers are excluded from the default
    # list view but stay fully intact for their existing orders.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    addresses: Mapped[list["Address"]] = relationship(back_populates="customer")


class Address(Base):
    __tablename__ = "addresses"

    address_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    # Denormalized per ARCHITECTURE.md Section 1, so tenant-scoped queries
    # don't need to join through Customer.
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    label: Mapped[str] = mapped_column(String(64))
    line1: Mapped[str] = mapped_column(String(255))
    line2: Mapped[str | None] = mapped_column(String(255), default=None)
    landmark: Mapped[str | None] = mapped_column(String(255), default=None)
    city: Mapped[str] = mapped_column(String(128))
    pincode: Mapped[str] = mapped_column(String(16))
    geo_lat: Mapped[float | None] = mapped_column(Float, default=None)
    geo_long: Mapped[float | None] = mapped_column(Float, default=None)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )

    customer: Mapped["Customer"] = relationship(back_populates="addresses")
