from sqlalchemy.ext.asyncio import AsyncSession

from campaigns.adapters.repository import MessageTemplateRepository
from conversation.domain.webhook_parser import TemplateStatusUpdate


async def apply_template_status_update(session: AsyncSession, update: TemplateStatusUpdate) -> None:
    """Applied by conversation/api/router.py's receive_webhook for every
    TemplateStatusUpdate parsed off an inbound payload -- a template whose
    meta_template_id isn't on file (e.g. deleted locally, or belongs to a
    different Meta App entirely) is silently skipped, same "nothing to act
    on" convention the rest of the webhook path follows rather than
    raising and breaking Meta's always-200 ack contract."""
    await MessageTemplateRepository(session).update_approval_status(
        update.meta_template_id, status=update.status, reason=update.reason
    )
