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
    """Not a stored single value -- see Merchant.restaurant_enabled /
    Merchant.appointment_enabled below (VERTICAL_TOGGLE_PLAN.md: a merchant
    can run either or both, and can add the other later from Settings, not
    just once at registration). This enum is still useful as a typed "which
    vertical" parameter (e.g. MerchantRepository.list_enabled_for_vertical),
    matching MULTI_VERTICAL_PLAN.md's Decision 6 that adding a third
    vertical should be a visible migration, not a silent string typo."""

    RESTAURANT = "restaurant"
    APPOINTMENT = "appointment"


class NoVerticalSelectedError(Exception):
    """restaurant_enabled and appointment_enabled can't both be False -- the
    one domain invariant both the onboarding entry point and the Settings
    add-on entry point validate through, per VERTICAL_TOGGLE_PLAN.md's "no
    separate code path or weaker validation just because it's onboarding.\""""


def validate_vertical_flags(*, restaurant_enabled: bool, appointment_enabled: bool) -> None:
    if not restaurant_enabled and not appointment_enabled:
        raise NoVerticalSelectedError("At least one of restaurant/appointment must be enabled")


class InvalidWebsiteUrlError(Exception):
    """Raised by normalize_website_url for a non-blank value that doesn't
    start with http:// or https://."""


def normalize_website_url(website_url: str | None) -> str | None:
    """Structural validation only -- no reachability/fetch check, that's an
    explicit future gap, not v1 scope. Blank/whitespace-only is the "clear
    the field" case, not an error."""
    if website_url is None:
        return None
    stripped = website_url.strip()
    if not stripped:
        return None
    if not (stripped.startswith("http://") or stripped.startswith("https://")):
        raise InvalidWebsiteUrlError("website_url must start with http:// or https://")
    return stripped


class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_name: Mapped[str] = mapped_column(String(255))
    owner_contact: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    onboarding_status: Mapped[str] = mapped_column(String(32), default="registered")
    status: Mapped[str] = mapped_column(String(16), default="active")

    # Set via PUT /api/v1/onboarding/verticals -- the onboarding wizard's
    # first step, and (unlike Phase 10's single `vertical` enum) freely
    # editable again later from Settings to add a second vertical. At least
    # one must always be True (validate_vertical_flags, enforced by
    # MerchantRepository.set_vertical_flags, the only writer for both).
    restaurant_enabled: Mapped[bool] = mapped_column(default=False)
    appointment_enabled: Mapped[bool] = mapped_column(default=False)

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

    # Merchant's own website, offered as a "Visit website" option in the
    # WhatsApp greeting menu when set -- see conversation/domain/handler.py.
    website_url: Mapped[str | None] = mapped_column(String(2048), default=None)

    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    staff_users: Mapped[list["StaffUser"]] = relationship(back_populates="merchant")


class WebsiteLinkClick(Base):
    """Append-only click log for the "Visit website" WhatsApp menu option --
    same pattern as PaymentEvent/OrderStatusEvent elsewhere in this
    codebase. No update/delete methods; the dashboard-facing stat is a
    count query over this table (WebsiteLinkClickRepository.count_since)."""

    __tablename__ = "website_link_clicks"

    click_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    clicked_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC), index=True
    )


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
