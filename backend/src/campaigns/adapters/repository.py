import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from campaigns.domain.models import Campaign, CampaignRecipient, MessageTemplate
from shared.tenant import TenantContext


class MessageTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        tenant: TenantContext,
        *,
        name: str,
        category: str,
        language_code: str,
        header_type: str,
        header_text: str | None,
        header_media_handle: str | None,
        body_text: str,
        body_variable_count: int,
        footer_text: str | None,
        buttons: list[dict[str, str | None]],
    ) -> MessageTemplate:
        template = MessageTemplate(
            merchant_id=tenant.merchant_id,
            name=name,
            category=category,
            language_code=language_code,
            header_type=header_type,
            header_text=header_text,
            header_media_handle=header_media_handle,
            body_text=body_text,
            body_variable_count=body_variable_count,
            footer_text=footer_text,
            buttons=buttons,
        )
        self._session.add(template)
        await self._session.flush()
        return template

    async def set_meta_submission_result(
        self, template: MessageTemplate, *, meta_template_id: str, status: str
    ) -> None:
        template.meta_template_id = meta_template_id
        template.meta_approval_status = status
        await self._session.flush()

    async def get(self, tenant: TenantContext, template_id: uuid.UUID) -> MessageTemplate | None:
        template = await self._session.get(MessageTemplate, template_id)
        if template is None or template.merchant_id != tenant.merchant_id:
            return None
        return template

    async def get_by_meta_template_id(self, meta_template_id: str) -> MessageTemplate | None:
        """Cross-tenant on purpose -- the message_template_status_update
        webhook only carries Meta's own template id, the same "resolve
        tenant from the Meta-side id" pattern onboarding/adapters/
        repository.py's get_by_phone_number_id/get_by_flow_id establish."""
        result = await self._session.execute(
            select(MessageTemplate).where(MessageTemplate.meta_template_id == meta_template_id)
        )
        return result.scalar_one_or_none()

    async def list(self, tenant: TenantContext) -> list[MessageTemplate]:
        result = await self._session.execute(
            select(MessageTemplate)
            .where(MessageTemplate.merchant_id == tenant.merchant_id)
            .order_by(MessageTemplate.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_approval_status(
        self, meta_template_id: str, *, status: str, reason: str | None
    ) -> MessageTemplate | None:
        template = await self.get_by_meta_template_id(meta_template_id)
        if template is None:
            return None
        template.meta_approval_status = status
        template.meta_rejection_reason = reason
        await self._session.flush()
        return template

    async def delete(self, tenant: TenantContext, template_id: uuid.UUID) -> MessageTemplate | None:
        template = await self.get(tenant, template_id)
        if template is None:
            return None
        await self._session.delete(template)
        await self._session.flush()
        return template


class CampaignRepository:
    # NOTE: every method whose signature spells out a bare `list[...]`
    # generic has to be defined above `list()` itself, below -- once that
    # method exists, its own name shadows the `list` builtin for every
    # annotation evaluated afterwards, in this class's namespace, for both
    # Python at runtime and mypy statically. Same footgun faq/adapters/
    # repository.py's FAQItemRepository documents and avoids.
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_due(self, now: datetime.datetime) -> list["Campaign"]:
        """Cross-tenant on purpose -- the scheduler job iterates every
        merchant's due work in one sweep, the same "no per-tenant polling"
        shape shared/scheduler.py's other jobs already use. "Due" is
        either a scheduled campaign whose time has arrived (or is unset,
        i.e. send-now) or a campaign still mid-send from a prior tick/day
        (overflow resumption, per send_orchestrator.py's tier-ceiling
        design)."""
        result = await self._session.execute(
            select(Campaign).where(
                (
                    (Campaign.status == "scheduled")
                    & ((Campaign.scheduled_at.is_(None)) | (Campaign.scheduled_at <= now))
                )
                | (Campaign.status == "sending")
            )
        )
        return list(result.scalars().all())

    async def create(
        self,
        tenant: TenantContext,
        *,
        name: str,
        template_id: uuid.UUID,
        audience_filter: dict[str, object],
        scheduled_at: datetime.datetime | None,
        created_by: str,
    ) -> Campaign:
        campaign = Campaign(
            merchant_id=tenant.merchant_id,
            name=name,
            template_id=template_id,
            audience_filter=audience_filter,
            scheduled_at=scheduled_at,
            created_by=created_by,
        )
        self._session.add(campaign)
        await self._session.flush()
        return campaign

    async def get(self, tenant: TenantContext, campaign_id: uuid.UUID) -> Campaign | None:
        campaign = await self._session.get(Campaign, campaign_id)
        if campaign is None or campaign.merchant_id != tenant.merchant_id:
            return None
        return campaign

    async def list(self, tenant: TenantContext) -> list[Campaign]:
        result = await self._session.execute(
            select(Campaign)
            .where(Campaign.merchant_id == tenant.merchant_id)
            .order_by(Campaign.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_fields(
        self,
        tenant: TenantContext,
        campaign_id: uuid.UUID,
        *,
        name: str | None = None,
        template_id: uuid.UUID | None = None,
        audience_filter: dict[str, object] | None = None,
        scheduled_at: datetime.datetime | None = None,
    ) -> Campaign | None:
        """Draft-only editing -- the router enforces the draft-only rule;
        this just applies whatever's given."""
        campaign = await self.get(tenant, campaign_id)
        if campaign is None:
            return None
        if name is not None:
            campaign.name = name
        if template_id is not None:
            campaign.template_id = template_id
        if audience_filter is not None:
            campaign.audience_filter = audience_filter
        if scheduled_at is not None:
            campaign.scheduled_at = scheduled_at
        await self._session.flush()
        return campaign

    async def set_status(
        self, campaign: Campaign, status: str, *, completed: bool = False
    ) -> None:
        campaign.status = status
        if completed:
            campaign.completed_at = datetime.datetime.now(datetime.UTC)
        await self._session.flush()


class CampaignRecipientRepository:
    # Same list()-shadowing footgun as CampaignRepository above -- every
    # list[...]-annotated method here is defined before list_pending()/
    # list_pending_for_customers(), which is fine (neither is named `list`),
    # but keep new methods above any future method literally named `list`.
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def materialize_pending(
        self, campaign_id: uuid.UUID, customer_ids: list[uuid.UUID]
    ) -> None:
        """Idempotent -- ON CONFLICT DO NOTHING against the (campaign_id,
        customer_id) unique constraint, so calling this again on a later
        tick (the audience is re-resolved fresh each time, per
        send_orchestrator.py) never duplicates a row for a customer
        already materialized on an earlier tick."""
        if not customer_ids:
            return
        stmt = (
            pg_insert(CampaignRecipient)
            .values(
                [
                    {"campaign_id": campaign_id, "customer_id": customer_id, "status": "pending"}
                    for customer_id in customer_ids
                ]
            )
            .on_conflict_do_nothing(index_elements=["campaign_id", "customer_id"])
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def list_pending(self, campaign_id: uuid.UUID, limit: int) -> list[CampaignRecipient]:
        result = await self._session.execute(
            select(CampaignRecipient)
            .where(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == "pending",
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_pending_for_customers(
        self, campaign_id: uuid.UUID, customer_ids: list[uuid.UUID]
    ) -> list[CampaignRecipient]:
        """Scoped to a known, already-in-memory set of customer ids (the
        just-resolved audience) rather than an unbounded scan -- used by
        send_orchestrator.py's opt-out/no-number skip pass, which has to
        look at every still-pending row for this tick's audience, not just
        the ones about to be sent."""
        if not customer_ids:
            return []
        result = await self._session.execute(
            select(CampaignRecipient).where(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == "pending",
                CampaignRecipient.customer_id.in_(customer_ids),
            )
        )
        return list(result.scalars().all())

    async def mark_sent(
        self, recipient: CampaignRecipient, *, whatsapp_message_id: str | None = None
    ) -> None:
        """whatsapp_message_id stays None for now -- WhatsAppSender.
        send_template_message (conversation/adapters/whatsapp_client.py)
        only returns a bool today, not Meta's message id, matching every
        existing caller's needs (none of them persist it either). The
        column exists as a forward-looking extension point (see
        CampaignRecipient's docstring) for whenever that changes."""
        recipient.status = "sent"
        recipient.sent_at = datetime.datetime.now(datetime.UTC)
        recipient.whatsapp_message_id = whatsapp_message_id
        await self._session.flush()

    async def mark_failed(self, recipient: CampaignRecipient, *, reason: str) -> None:
        recipient.status = "failed"
        recipient.failure_reason = reason
        await self._session.flush()

    async def mark_skipped(self, recipient: CampaignRecipient, *, status: str) -> None:
        recipient.status = status
        await self._session.flush()

    async def counts_by_status(self, campaign_id: uuid.UUID) -> dict[str, int]:
        result = await self._session.execute(
            select(CampaignRecipient.status, func.count())
            .where(CampaignRecipient.campaign_id == campaign_id)
            .group_by(CampaignRecipient.status)
        )
        return {status: count for status, count in result.all()}

    async def has_pending(self, campaign_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            select(CampaignRecipient.recipient_id)
            .where(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == "pending",
            )
            .limit(1)
        )
        return result.first() is not None

    async def count_sent_today(
        self, tenant: TenantContext, *, day_start: datetime.datetime, day_end: datetime.datetime
    ) -> int:
        """Scoped to `tenant` via a join through Campaign (CampaignRecipient
        itself carries no merchant_id -- unlike Address's denormalization,
        this is an internal scheduler-batch query, not a per-request API
        path, so a join here costs nothing meaningful)."""
        result = await self._session.execute(
            select(func.count())
            .select_from(CampaignRecipient)
            .join(Campaign, Campaign.campaign_id == CampaignRecipient.campaign_id)
            .where(
                Campaign.merchant_id == tenant.merchant_id,
                CampaignRecipient.status == "sent",
                CampaignRecipient.sent_at >= day_start,
                CampaignRecipient.sent_at < day_end,
            )
        )
        return int(result.scalar_one())
