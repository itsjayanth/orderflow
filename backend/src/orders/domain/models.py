import datetime
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from customers.domain.models import Customer
from shared.db import Base


class MerchantOrderCounter(Base):
    """One row per merchant, tracking the next order_number to hand out.
    Order.order_number is assigned by an atomic upsert against this table
    (see orders/adapters/repository.py's `_next_order_number`) rather than
    e.g. `SELECT MAX(order_number) + 1 FROM orders`, which isn't safe
    against concurrent inserts without extra locking. A per-merchant
    sequence (not a global one, and not a Postgres SEQUENCE object, which
    can't be created per-merchant without dynamic DDL) keeps each
    merchant's numbers starting at 1 and gap-free under normal operation."""

    __tablename__ = "merchant_order_counters"

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("merchants.merchant_id"), primary_key=True
    )
    next_order_number: Mapped[int] = mapped_column(default=1)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("merchant_id", "order_number"),)

    order_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.customer_id"), index=True)

    # Human-facing sequential reference (per merchant, starts at 1, never
    # reused/reset) -- shown in the dashboard, order detail pages, and
    # WhatsApp messages instead of the UUID primary key. See
    # MerchantOrderCounter above for how it's assigned.
    order_number: Mapped[int] = mapped_column()

    order_type: Mapped[str] = mapped_column(String(16))  # "pickup" | "delivery"
    delivery_address_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("addresses.address_id"), default=None
    )
    payment_method: Mapped[str] = mapped_column(String(16))  # "online" | "cod"

    # See orders/domain/state_machine.py for the allowed values and
    # transitions of both fields -- Order is deliberately the only place
    # that mutates them, always through that module's transition functions.
    payment_status: Mapped[str] = mapped_column(String(32))
    # Null until payment_status reaches "paid" or "cod_pending" -- the order
    # isn't in the kitchen workflow yet (ARCHITECTURE.md Section 7b's gate).
    fulfillment_status: Mapped[str | None] = mapped_column(String(32), default=None)

    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(8), default="INR")

    whatsapp_conversation_ref: Mapped[str | None] = mapped_column(String(255), default=None)
    # Phase 2 (POS integration) seam -- unused until then.
    external_pos_order_id: Mapped[str | None] = mapped_column(String(255), default=None)

    placed_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
    paid_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
    ready_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    # No back_populates on Customer -- nothing there needs the reverse
    # collection today, and adding it would be an unused surface.
    customer: Mapped["Customer"] = relationship()


class OrderItem(Base):
    __tablename__ = "order_items"

    order_item_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.order_id"), index=True)
    menu_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("menu_items.menu_item_id"))

    name_snapshot: Mapped[str] = mapped_column(String(255))
    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    quantity: Mapped[int] = mapped_column()
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    order: Mapped["Order"] = relationship(back_populates="items")


class OrderStatusEvent(Base):
    """Append-only audit trail of fulfillment_status transitions only --
    payment transitions live in PaymentEvent (Phase 5)."""

    __tablename__ = "order_status_events"

    status_event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.order_id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32), default=None)
    to_status: Mapped[str] = mapped_column(String(32))
    # staff_user_id as str, or "system" (e.g. a future Phase 2 POS push).
    changed_by: Mapped[str] = mapped_column(String(64))
    notified_customer: Mapped[bool] = mapped_column(default=False)
    changed_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
