import datetime
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class MerchantItemCounter(Base):
    """One row per merchant, tracking the next item_number to hand out --
    same pattern as orders/domain/models.py's MerchantOrderCounter (see its
    docstring for why a dedicated counter table beats MAX()+1 or a Postgres
    SEQUENCE here)."""

    __tablename__ = "merchant_item_counters"

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("merchants.merchant_id"), primary_key=True
    )
    next_item_number: Mapped[int] = mapped_column(default=1)


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("merchant_id", "item_number"),)

    item_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    # Human-facing sequential reference (per merchant, starts at 1, never
    # reused/reset) -- shown in the dashboard catalog table and usable as a
    # search filter, same role order_number plays for orders.
    item_number: Mapped[int] = mapped_column()
    category: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    is_available: Mapped[bool] = mapped_column(default=True)
    # Merchant-supplied URL to an already-hosted photo (their own hosting, a
    # stock photo, etc.) -- there's no file-upload/CDN infrastructure in this
    # app, so images are "paste a URL" rather than an upload flow. Nullable:
    # NULL means "no image set", rendered as a fallback in both the merchant
    # catalog and the public ordering webview.
    image_url: Mapped[str | None] = mapped_column(String(2048), default=None)
    # Base64 JPEG, re-encoded down to ~20KB from image_url and cached here on
    # first use (see flows/domain/images.py) -- WhatsApp Flow CheckboxGroup
    # options can embed an image directly, but caps it at 100KB (Flow JSON
    # v5.0+) and explicitly recommends staying well under that; fetching and
    # recompressing image_url on every Flow screen load would also make
    # every category view noticeably slower, hence caching the result
    # instead of doing this live each time. NULL until first requested, or
    # if image_url is unset/unreachable.
    flow_image_base64: Mapped[str | None] = mapped_column(Text, default=None)
    # Phase 2 (POS integration) seam — unused until then, per ARCHITECTURE.md Section 1.
    external_pos_item_id: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
