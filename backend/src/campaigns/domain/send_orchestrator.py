import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from campaigns.adapters.repository import CampaignRecipientRepository
from campaigns.domain.audience import resolve_audience
from campaigns.domain.models import Campaign, CampaignRecipient, MessageTemplate
from conversation.adapters.whatsapp_client import WhatsAppSender
from customers.domain.models import Customer
from identity.adapters.repository import MerchantRepository
from onboarding.domain.models import WhatsAppBusinessAccount
from shared.encryption import decrypt
from shared.tenant import TenantContext

logger = logging.getLogger(__name__)

# Rate-limiting beyond the daily tier cap (the roadmap ticket's own "avoid
# tripping Meta's per-number throughput limits" criterion) -- a fixed
# per-tick batch size, throttled by the scheduler's existing 5-minute tick
# interval rather than a token-bucket or explicit delay, so a large
# campaign fans out over several ticks by construction. A placeholder
# tuned to no live-volume data, not derived from any documented Meta
# throughput number (none is consistently published) -- see
# docs/broadcast-implementation-plan.md's Open Questions.
_MAX_SENDS_PER_TICK = 50


def _body_params(template: MessageTemplate, customer_name: str, business_name: str) -> list[str]:
    """v1 scope: only customer name and business name, in that order,
    truncated or padded to the template's declared variable count -- a
    broadcast campaign isn't tied to a single order the way lifecycle
    notifications are, so there's no richer per-recipient context (last
    order items, an offer amount) to draw on yet. See
    docs/broadcast-implementation-plan.md's Assumptions."""
    values = [customer_name, business_name]
    if template.body_variable_count <= len(values):
        return values[: template.body_variable_count]
    return values + [""] * (template.body_variable_count - len(values))


async def _skip_ineligible_recipients(
    recipient_repo: CampaignRecipientRepository,
    campaign_id: uuid.UUID,
    customers_by_id: dict[uuid.UUID, Customer],
) -> list[CampaignRecipient]:
    """Marks every still-pending row for an opted-out (Phase 12) or
    number-less customer as skipped, then returns the remaining
    genuinely-sendable pending rows for this tick's audience. Run on
    every tick, not just the first, so a customer who opts out mid-run
    stops being included in subsequent ticks' sends."""
    pending = await recipient_repo.list_pending_for_customers(
        campaign_id, list(customers_by_id.keys())
    )
    sendable: list[CampaignRecipient] = []
    for recipient in pending:
        customer = customers_by_id[recipient.customer_id]
        if customer.marketing_opt_out:
            await recipient_repo.mark_skipped(recipient, status="skipped_opted_out")
        elif not customer.whatsapp_number:
            # Defensive only -- whatsapp_number is the identity key
            # find_or_create() requires, so this can't happen today.
            await recipient_repo.mark_skipped(recipient, status="skipped_no_number")
        else:
            sendable.append(recipient)
    return sendable


async def send_campaign_batch(
    session: AsyncSession,
    tenant: TenantContext,
    campaign: Campaign,
    waba: WhatsAppBusinessAccount,
    sender: WhatsAppSender,
    quota_remaining: int,
) -> int:
    """Resolves the audience fresh (excluding nothing -- opted-out/
    number-less customers are included so their skip is recorded, not
    silently absent), materializes CampaignRecipient rows on first run
    (idempotent on later ticks), then sends up to
    min(quota_remaining, _MAX_SENDS_PER_TICK) pending rows via the exact
    same WhatsAppSender.send_template_message method
    notifications/adapters/whatsapp_channel.py's appointment-reminder
    path already calls -- the literal reuse of conversation/adapters/
    whatsapp_client.py's send path the roadmap ticket asks for. Returns
    the number of recipients actually sent to, for the scheduler's log
    line."""
    if quota_remaining <= 0:
        return 0

    recipient_repo = CampaignRecipientRepository(session)
    customers = await resolve_audience(session, tenant, campaign.audience_filter)
    await recipient_repo.materialize_pending(
        campaign.campaign_id, [c.customer_id for c in customers]
    )
    await session.commit()

    customers_by_id = {c.customer_id: c for c in customers}
    sendable = await _skip_ineligible_recipients(
        recipient_repo, campaign.campaign_id, customers_by_id
    )
    await session.commit()

    if not sendable:
        return 0

    template = await session.get(MessageTemplate, campaign.template_id)
    if template is None:
        logger.warning("Campaign %s references a deleted template", campaign.campaign_id)
        return 0
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    business_name = merchant.business_name if merchant else ""
    access_token = decrypt(waba.access_token_encrypted) if waba.access_token_encrypted else ""

    to_send = sendable[: min(quota_remaining, _MAX_SENDS_PER_TICK)]
    sent_count = 0
    for recipient in to_send:
        customer = customers_by_id[recipient.customer_id]
        # Never raises -- send_template_message follows this codebase's
        # existing best-effort outbound-send convention (logged, returns
        # False on failure) everywhere else.
        success = await sender.send_template_message(
            phone_number_id=waba.phone_number_id or "",
            access_token=access_token,
            to=customer.whatsapp_number,
            template_name=template.name,
            language_code=template.language_code,
            body_params=_body_params(template, customer.display_name or "", business_name),
        )
        if success:
            await recipient_repo.mark_sent(recipient)
            sent_count += 1
        else:
            await recipient_repo.mark_failed(recipient, reason="WhatsApp send failed")

    await session.commit()
    return sent_count
