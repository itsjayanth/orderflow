import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from campaigns.adapters.repository import CampaignRepository
from campaigns.domain.audience import validate_audience_filter
from campaigns.domain.models import Campaign
from shared.tenant import TenantContext


async def create_campaign(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    name: str,
    template_id: uuid.UUID,
    audience_filter: dict[str, object],
    scheduled_at: datetime.datetime | None,
    created_by: str,
) -> Campaign:
    """Same-process domain function, callable directly (not just through
    campaigns/api/router.py's HTTP endpoint) -- the interface point the
    roadmap's not-yet-built Automated Reorder Reminder and Lost Customer
    Win-back scheduled jobs will call with created_by="system:<job-name>",
    matching this codebase's existing convention of cross-module calls as
    plain function calls within one deployed process (onboarding/domain/
    onboarding_service.py's catalog_ready gate calling into Catalog/
    Appointment Service the same way). Does not commit -- callers commit,
    same convention as every other *_service.py function."""
    validate_audience_filter(audience_filter)
    return await CampaignRepository(session).create(
        tenant,
        name=name,
        template_id=template_id,
        audience_filter=audience_filter,
        scheduled_at=scheduled_at,
        created_by=created_by,
    )
