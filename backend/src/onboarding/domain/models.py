import datetime
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class WhatsAppBusinessAccount(Base):
    """One per Merchant (MVP single-outlet assumption), per ARCHITECTURE.md
    Section 1. `connection_status` is set from whether phone_number_id and
    access_token are both present, not a real Meta OAuth handshake yet --
    the merchant pastes these values directly (a legitimate WhatsApp Cloud
    API connection method, not just a placeholder for later)."""

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

    # A second, independent Flow object for native in-chat appointment
    # booking (see flows/assets/appointment_flow.json) -- shares the same
    # business-level RSA key pair as whatsapp_flow_id above (Meta's
    # whatsapp_business_encryption key is per phone_number_id, not per
    # Flow), so there's no separate private-key column here.
    whatsapp_appointment_flow_id: Mapped[str | None] = mapped_column(String(255), default=None)

    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
