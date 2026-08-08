import datetime
import uuid

from sqlalchemy import Boolean, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db import Base


class MerchantCustomerCounter(Base):
    """One row per merchant, tracking the next customer_number to hand out
    -- same pattern as orders/domain/models.py's MerchantOrderCounter and
    catalog/domain/models.py's MerchantMenuItemCounter (see either for why
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
    # and menu items. Shown in the dashboard, orders, and customers UI, and
    # usable as a search filter, instead of the raw customer_id UUID.
    customer_number: Mapped[int] = mapped_column()
    whatsapp_number: Mapped[str] = mapped_column(String(32))
    display_name: Mapped[str | None] = mapped_column(String(255), default=None)
    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
    last_order_at: Mapped[datetime.datetime | None] = mapped_column(default=None)

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
