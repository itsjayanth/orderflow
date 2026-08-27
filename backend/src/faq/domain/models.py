import datetime
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class FAQItem(Base):
    __tablename__ = "faq_items"

    faq_item_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    question_text: Mapped[str] = mapped_column(String(500))
    answer_text: Mapped[str] = mapped_column(Text)
    # Merchant-authored trigger words/phrases matched against inbound WhatsApp
    # text (see faq/adapters/repository.py's match()) -- not the question
    # text itself, since customers paraphrase rather than typing the question
    # verbatim.
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String(255)))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
