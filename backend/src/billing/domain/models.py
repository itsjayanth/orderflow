import datetime
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class Plan(Base):
    """Global reference data -- one row per (tier, billing_interval) pair,
    not per tier. Razorpay Subscriptions Plans are single-price/single-
    interval objects (a Plan can't be parameterized by interval), so the
    local model mirrors that 1:1 rather than inventing a richer shape
    Razorpay itself doesn't support. Seeded once by the migration that
    creates this table (see the accompanying Alembic revision); never
    written to by application code, so this repository/model pair has no
    TenantContext -- it isn't tenant data at all."""

    __tablename__ = "billing_plans"
    __table_args__ = (UniqueConstraint("tier", "billing_interval"),)

    plan_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tier: Mapped[str] = mapped_column(String(16))  # "starter" | "growth" | "pro"
    billing_interval: Mapped[str] = mapped_column(String(16))  # "monthly" | "annual"
    display_name: Mapped[str] = mapped_column(String(64))
    price_inr: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    order_cap: Mapped[int | None] = mapped_column(default=None)  # None = unlimited (Pro)
    whatsapp_flow_enabled: Mapped[bool] = mapped_column(default=False)
    branding_required: Mapped[bool] = mapped_column(default=True)
    # Unset (NULL) for every seeded row today -- dummy-gateway mode until a
    # real platform Razorpay account exists and these are backfilled via
    # the Razorpay dashboard/API. See billing/adapters/gateway_selector.py.
    razorpay_plan_id: Mapped[str | None] = mapped_column(String(255), default=None)


class Subscription(Base):
    """1:1 with Merchant -- merchant_id is the PK itself, same shape as
    payments/domain/models.py's MerchantPaymentCredentials. Created in the
    same transaction as Merchant/StaffUser at registration time
    (identity/domain/auth.py), always starting `trialing`."""

    __tablename__ = "subscriptions"

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("merchants.merchant_id"), primary_key=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("billing_plans.plan_id"))

    # See billing/domain/state_machine.py for the allowed values and
    # transitions -- Subscription is deliberately the only place that
    # mutates `status`, always through transition_subscription_status.
    status: Mapped[str] = mapped_column(String(16))  # trialing|active|past_due|canceled|expired

    trial_ends_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
    current_period_start: Mapped[datetime.datetime | None] = mapped_column(default=None)
    current_period_end: Mapped[datetime.datetime | None] = mapped_column(default=None)
    # Set when status enters "past_due", cleared when it leaves -- backs
    # billing/domain/gating.py's grace-period check.
    past_due_since: Mapped[datetime.datetime | None] = mapped_column(default=None)
    # User-initiated cancellation is deferred to period end (never an
    # immediate service cutoff) -- status itself only flips to "canceled"
    # once the webhook (or the sweep job) confirms the period has actually
    # ended.
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(255), default=None)

    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )


class BillingEvent(Base):
    """Append-only -- the audit trail for every platform-billing webhook
    received (or synthesized by the sweep job), mirroring
    payments/domain/models.py's PaymentEvent exactly: no DB unique
    constraint, dedupe is application-level via provider_payment_id."""

    __tablename__ = "billing_events"

    billing_event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)

    provider: Mapped[str] = mapped_column(String(32))  # "razorpay" | "dummy"
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), index=True, default=None)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(255), default=None)

    # subscription.activated | .charged | .pending | .halted | .cancelled |
    # payment.failed | webhook_received_duplicate | order_cap_exceeded
    event_type: Mapped[str] = mapped_column(String(64))
    raw_payload: Mapped[str | None] = mapped_column(Text, default=None)

    received_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
