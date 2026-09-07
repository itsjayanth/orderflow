import datetime
import uuid

from sqlalchemy import Boolean, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Text, TypeDecorator

from shared.db import Base
from shared.encryption import decrypt, encrypt


class FernetEncryptedString(TypeDecorator[str]):
    """Transparently Fernet-encrypts a string column at the SQLAlchemy
    bind/result boundary, reusing shared/encryption.py's encrypt()/decrypt()
    (the same Fernet cipher already used for WhatsApp/Razorpay credentials)
    -- not a new encryption system, just this one wrapped in a Type so it
    applies uniformly to every load path.

    Deliberately NOT this codebase's usual convention of explicit encrypt()/
    decrypt() calls at the repository boundary (see e.g. payments/adapters/
    gateway_selector.py, onboarding/api/router.py): Customer and Address
    rows are routinely loaded elsewhere in the app via a plain SQLAlchemy
    relationship -- Order.customer/Order.delivery_address, Appointment.
    customer (selectinload'd in orders/adapters/repository.py and
    appointments/adapters/repository.py) -- entirely bypassing
    CustomerRepository/AddressRepository. notifications/adapters/
    whatsapp_channel.py then sends `to=customer.whatsapp_number` straight
    to Meta's API from one of those relationship loads. An explicit
    decrypt-at-this-module's-repository-boundary would leave every one of
    those other call sites reading raw ciphertext -- notifications would
    silently try to message a base64 blob instead of a phone number. A
    transparent column type is the smallest fix that is correct on every
    load path without editing those other modules.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return decrypt(value)


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
        # The unique/dedup constraint lives on whatsapp_number_lookup_hash,
        # not on whatsapp_number itself -- Fernet's ciphertext is
        # non-deterministic (random IV per call), so two encryptions of the
        # identical phone number never compare equal, and a DB-level unique
        # constraint on the ciphertext column would be meaningless. The
        # HMAC lookup hash is deterministic and is the real identity key
        # here; whatsapp_number is kept only as the (encrypted) display/
        # send-target value. See CustomerRepository for the read/write side
        # of this split.
        UniqueConstraint(
            "merchant_id",
            "whatsapp_number_lookup_hash",
            name="uq_customers_merchant_whatsapp_hash",
        ),
        UniqueConstraint("merchant_id", "customer_number", name="uq_customers_merchant_number"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    # Human-facing sequential reference (per merchant, starts at 1, never
    # reused/reset) -- same role order_number/item_number play for orders
    # and items. Shown in the dashboard, orders, and customers UI, and
    # usable as a search filter, instead of the raw customer_id UUID.
    customer_number: Mapped[int] = mapped_column()
    # Stored Fernet-encrypted at rest (FernetEncryptedString transparently
    # encrypts/decrypts -- reads back as plaintext everywhere the ORM loads
    # this column, direct query or relationship traversal alike). Text, not
    # a bounded String: a Fernet token is meaningfully longer than a phone
    # number and grows with plaintext length.
    whatsapp_number: Mapped[str] = mapped_column(FernetEncryptedString)
    # Deterministic HMAC-SHA256(whatsapp_number, secrets_encryption_key) hex
    # digest -- the actual lookup/dedup key now that whatsapp_number itself
    # is non-deterministic ciphertext (see __table_args__ above).
    # CustomerRepository computes this on every write and queries by it
    # instead of by whatsapp_number. Indexed: this is the hottest read path
    # in the app (every inbound WhatsApp webhook message).
    whatsapp_number_lookup_hash: Mapped[str] = mapped_column(String(64), index=True)
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
    # WhatsApp Business Platform policy: honoring STOP/opt-out is mandatory
    # for MARKETING-category sends (broadcast campaigns), not optional
    # polish -- conversation/domain/handler.py's Intent.OPT_OUT/OPT_IN
    # branch is the only writer, driven by the customer's own STOP/START
    # message. Deliberately does NOT gate transactional notifications
    # (notifications/adapters/whatsapp_channel.py's order/appointment
    # lifecycle sends) -- Meta treats those as a different message
    # category entirely, and nothing in that channel reads this flag.
    marketing_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    marketing_opt_out_at: Mapped[datetime.datetime | None] = mapped_column(default=None)

    addresses: Mapped[list["Address"]] = relationship(back_populates="customer")


class Address(Base):
    __tablename__ = "addresses"

    address_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    # Denormalized per ARCHITECTURE.md Section 1, so tenant-scoped queries
    # don't need to join through Customer.
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    label: Mapped[str] = mapped_column(String(64))
    # PII, Fernet-encrypted at rest via FernetEncryptedString (see that
    # type's docstring) -- unlike whatsapp_number these are never queried
    # by value (only ever displayed, or matched by address_id/customer_id),
    # so no lookup-hash companion column is needed here.
    line1: Mapped[str] = mapped_column(FernetEncryptedString)
    line2: Mapped[str | None] = mapped_column(FernetEncryptedString, default=None)
    landmark: Mapped[str | None] = mapped_column(FernetEncryptedString, default=None)
    city: Mapped[str] = mapped_column(FernetEncryptedString)
    pincode: Mapped[str] = mapped_column(FernetEncryptedString)
    geo_lat: Mapped[float | None] = mapped_column(Float, default=None)
    geo_long: Mapped[float | None] = mapped_column(Float, default=None)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )

    customer: Mapped["Customer"] = relationship(back_populates="addresses")
