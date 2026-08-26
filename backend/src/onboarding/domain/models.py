import datetime
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class WhatsAppBusinessAccount(Base):
    """One per Merchant (MVP single-outlet assumption), per ARCHITECTURE.md
    Section 1. Two ways to populate this row, tracked by `connection_method`:
    the merchant pastes phone_number_id + access_token directly ("manual",
    a legitimate WhatsApp Cloud API connection method, not just a
    placeholder for later), or they complete Meta's WhatsApp Embedded
    Signup ("embedded_signup", see onboarding/domain/embedded_signup.py),
    which drives the real Meta OAuth handshake and yields the same fields.
    Everything downstream (conversation/adapters/whatsapp_client.py,
    notifications, flows) reads phone_number_id/access_token_encrypted off
    this row regardless of which method set them -- credential-source-
    agnostic by construction, not by any special-casing."""

    __tablename__ = "whatsapp_business_accounts"

    waba_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("merchants.merchant_id"), unique=True, index=True
    )

    meta_waba_id: Mapped[str | None] = mapped_column(String(255), default=None)
    phone_number_id: Mapped[str | None] = mapped_column(String(255), default=None)
    display_phone_number: Mapped[str | None] = mapped_column(String(32), default=None)
    access_token_encrypted: Mapped[str | None] = mapped_column(String(2048), default=None)
    token_expiry_at: Mapped[datetime.datetime | None] = mapped_column(default=None)

    # "manual" | "embedded_signup"
    connection_method: Mapped[str] = mapped_column(String(32), default="manual")
    # The 6-digit PIN registered against phone_number_id via the Embedded
    # Signup setup call (POST /{phone_number_id}/register) -- Meta requires
    # this PIN again for any future re-registration of the same number, so
    # it's kept on file rather than only used once and discarded.
    two_step_pin_encrypted: Mapped[str | None] = mapped_column(String(255), default=None)

    # "pending" | "connected" | "token_expired" | "disconnected"
    connection_status: Mapped[str] = mapped_column(String(32), default="pending")
    webhook_subscribed: Mapped[bool] = mapped_column(default=False)
    connected_at: Mapped[datetime.datetime | None] = mapped_column(default=None)

    # WhatsApp Flows (native in-chat ordering) -- set once by the one-time
    # setup script (scripts/setup_whatsapp_flow.py), not through the normal
    # onboarding UI. flow_private_key_encrypted holds the RSA private key
    # half of the pair whose public half was uploaded to Meta via
    # POST /{phone_number_id}/whatsapp_business_encryption; flows/api/router.py's
    # data-exchange endpoint uses it to decrypt each screen request.
    whatsapp_flow_id: Mapped[str | None] = mapped_column(String(255), default=None)
    flow_private_key_encrypted: Mapped[str | None] = mapped_column(String(4096), default=None)

    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
