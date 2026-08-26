import datetime
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db import Base

# ARCHITECTURE.md Section 5.
ONBOARDING_STATUSES = (
    "registered",
    "meta_connected",
    "whatsapp_verified",
    "profile_completed",
    "catalog_ready",
    "live",
)


class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_name: Mapped[str] = mapped_column(String(255))
    owner_contact: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    onboarding_status: Mapped[str] = mapped_column(String(32), default="registered")
    status: Mapped[str] = mapped_column(String(16), default="active")

    # Business details (ARCHITECTURE.md Section 1's `kitchen_details`), all
    # nullable until the onboarding wizard's "business details" step is
    # completed. License number is explicitly optional per the brief.
    business_address_line1: Mapped[str | None] = mapped_column(String(255), default=None)
    business_address_line2: Mapped[str | None] = mapped_column(String(255), default=None)
    business_city: Mapped[str | None] = mapped_column(String(120), default=None)
    business_pincode: Mapped[str | None] = mapped_column(String(16), default=None)
    business_category: Mapped[str | None] = mapped_column(String(120), default=None)
    license_no: Mapped[str | None] = mapped_column(String(64), default=None)
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
