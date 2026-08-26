import uuid
from typing import Protocol


class NotificationChannel(Protocol):
    """One method per notification kind rather than a generic
    `notify(message)` -- keeps the actual message copy (and, later, which
    ones need an approved WhatsApp template outside the 24h customer-
    initiated window, per ARCHITECTURE.md Section 8) owned by the adapter,
    not scattered across every call site."""

    async def notify_order_confirmed(
        self, *, merchant_id: uuid.UUID, order_id: uuid.UUID
    ) -> bool: ...

    async def notify_order_processing(
        self, *, merchant_id: uuid.UUID, order_id: uuid.UUID
    ) -> bool: ...

    async def notify_order_ready(
        self, *, merchant_id: uuid.UUID, order_id: uuid.UUID
    ) -> bool: ...

    async def notify_order_completed(
        self, *, merchant_id: uuid.UUID, order_id: uuid.UUID
    ) -> bool: ...
