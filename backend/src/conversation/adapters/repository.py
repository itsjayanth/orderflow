import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from conversation.domain.models import ProcessedWhatsAppMessage


class MessageDedupeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def already_processed(self, whatsapp_message_id: str) -> bool:
        result = await self._session.execute(
            select(ProcessedWhatsAppMessage.processed_message_id).where(
                ProcessedWhatsAppMessage.whatsapp_message_id == whatsapp_message_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def mark_processed(self, whatsapp_message_id: str, merchant_id: uuid.UUID) -> bool:
        """Returns True if this call is the one that actually recorded it
        (i.e. no other concurrent request beat it) -- an ON CONFLICT DO
        NOTHING upsert, so two nearly-simultaneous deliveries of the same
        webhook can't both pass the dedupe check."""
        stmt = (
            insert(ProcessedWhatsAppMessage)
            .values(whatsapp_message_id=whatsapp_message_id, merchant_id=merchant_id)
            .on_conflict_do_nothing(index_elements=["whatsapp_message_id"])
            .returning(ProcessedWhatsAppMessage.processed_message_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
