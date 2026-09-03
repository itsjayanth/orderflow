import datetime
import uuid
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db import Base

# ARCHITECTURE.md Section 5. `vertical_selected` sits right after
# `registered` -- MULTI_VERTICAL_PLAN.md's Decision 4: the vertical choice
# is the very first wizard step, before WhatsApp connection, so every step
# after it (including which WhatsApp Flow a merchant is offered, see
# conversation/domain/handler.py) already knows the vertical.
ONBOARDING_STATUSES = (
    "registered",
    "vertical_selected",
    "meta_connected",
    "whatsapp_verified",
    "profile_completed",
    "catalog_ready",
    "live",
)


class MerchantVertical(StrEnum):
    """A merchant is exactly one of these, chosen once at onboarding and
    never changed afterwards (MerchantRepository.set_vertical raises if
    called a second time) -- MULTI_VERTICAL_PLAN.md's Decision 6: an enum,
    not a free string, so adding a third vertical is a visible migration,
    not a silent typo."""

    RESTAURANT = "restaurant"
    APPOINTMENT = "appointment"


class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_name: Mapped[str] = mapped_column(String(255))
    owner_contact: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    onboarding_status: Mapped[str] = mapped_column(String(32), default="registered")
    status: Mapped[str] = mapped_column(String(16), default="active")

    # Set once via PUT /api/v1/onboarding/vertical (the new first wizard
    # step) and never changed after -- nullable because it's unset for the
    # brief window between registration and that step. MerchantRepository
    # .set_vertical() is the only writer and enforces the immutability.
    vertical: Mapped[str | None] = mapped_column(String(16), default=None)

    # Business details (ARCHITECTURE.md Section 1's "business details"), all
    # nullable until the onboarding wizard's "business details" step is
    # completed. License number is explicitly optional per the brief.
    business_address_line1: Mapped[str | None] = mapped_column(String(255), default=None)
    business_address_line2: Mapped[str | None] = mapped_column(String(255), default=None)
    business_city: Mapped[str | None] = mapped_column(String(120), default=None)
    business_pincode: Mapped[str | None] = mapped_column(String(16), default=None)
    business_category: Mapped[str | None] = mapped_column(String(120), default=None)
    license_no: Mapped[str | None] = mapped_column(String(64), default=None)

    # IANA timezone name -- appointment_flow/domain/booking.py's past-date
    # check and appointment_flow/domain/availability.py's slot computation
    # both need "today"/"now" in the merchant's own local time, not UTC (a
    # merchant near UTC midnight would otherwise see slots wrongly
    # accepted/rejected). Defaults to India since that's this product's
    # primary market today; not auto-detected from anything.
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")

    # Hours-before-appointment offsets the reminder scan
    # (shared/scheduler.py's send_due_appointment_reminders) sends a
    # WhatsApp reminder at, e.g. [24, 2] for "a day before and two hours
    # before". Empty list = reminders off for this merchant. Defaults to a
    # single 24h reminder, not an empty list, so a merchant who never
    # visits the reminder settings still gets the baseline behavior the
    # product spec calls for.
    reminder_offsets_hours: Mapped[list[int]] = mapped_column(JSON, default=lambda: [24])

    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    staff_users: Mapped[list["StaffUser"]] = relationship(back_populates="merchant")


class StaffUser(Base):
    __tablename__ = "staff_users"

    staff_user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    email_or_phone: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="owner")
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="staff_users")
