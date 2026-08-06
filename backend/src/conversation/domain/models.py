import datetime
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class ProcessedWhatsAppMessage(Base):
    """Inbound WhatsApp webhooks are at-least-once delivery (ARCHITECTURE.md
    Section 8) -- dedupe by WhatsApp message ID before acting on one."""

    __tablename__ = "processed_whatsapp_messages"

    processed_message_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    whatsapp_message_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    processed_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
