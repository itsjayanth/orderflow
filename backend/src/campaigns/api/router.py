import base64
import binascii
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from campaigns.adapters.media_upload import MediaUploadError, upload_header_image
from campaigns.adapters.repository import (
    CampaignRecipientRepository,
    CampaignRepository,
    MessageTemplateRepository,
)
from campaigns.adapters.template_gateway import MetaTemplateGateway, TemplateGatewayError
from campaigns.api.schemas import (
    CampaignCreate,
    CampaignDetailOut,
    CampaignOut,
    CampaignRecipientCountsOut,
    CampaignUpdate,
    MessageTemplateCreate,
    MessageTemplateOut,
)
from campaigns.domain.audience import InvalidAudienceFilterError, validate_audience_filter
from campaigns.domain.campaign_service import create_campaign
from campaigns.domain.models import Campaign
from campaigns.domain.template_validation import InvalidTemplateError, normalize_template_name
from campaigns.domain.template_validation import validate_template as validate_template_fields
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from shared.deps import CurrentStaffUserId, CurrentTenant, DbSession

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


async def _detail_out(session: AsyncSession, campaign: Campaign) -> CampaignDetailOut:
    counts = await CampaignRecipientRepository(session).counts_by_status(campaign.campaign_id)
    return CampaignDetailOut(
        **CampaignOut.model_validate(campaign).model_dump(),
        recipient_counts=CampaignRecipientCountsOut(**counts),
    )


@router.get("/templates", response_model=list[MessageTemplateOut])
async def list_templates(tenant: CurrentTenant, session: DbSession) -> list[MessageTemplateOut]:
    templates = await MessageTemplateRepository(session).list(tenant)
    return [MessageTemplateOut.model_validate(t) for t in templates]


@router.get("/templates/{template_id}", response_model=MessageTemplateOut)
async def get_template(
    template_id: uuid.UUID, tenant: CurrentTenant, session: DbSession
) -> MessageTemplateOut:
    template = await MessageTemplateRepository(session).get(tenant, template_id)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return MessageTemplateOut.model_validate(template)


@router.post("/templates", response_model=MessageTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: MessageTemplateCreate, tenant: CurrentTenant, session: DbSession
) -> MessageTemplateOut:
    try:
        name = normalize_template_name(body.name)
        body_variable_count = validate_template_fields(
            category=body.category,
            header_type=body.header_type,
            header_text=body.header_text,
            body_text=body.body_text,
            footer_text=body.footer_text,
        )
    except InvalidTemplateError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
    if waba is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Connect WhatsApp before creating a template."
        )

    header_media_handle: str | None = None
    if body.header_type == "IMAGE":
        if not body.header_image_base64 or not body.header_image_content_type:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "header_image_base64 and header_image_content_type are required for an "
                "IMAGE header.",
            )
        try:
            image_bytes = base64.b64decode(body.header_image_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "header_image_base64 is not valid base64."
            ) from exc
        try:
            header_media_handle = await upload_header_image(
                waba, image_bytes, body.header_image_content_type
            )
        except MediaUploadError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    template = await MessageTemplateRepository(session).create(
        tenant,
        name=name,
        category=body.category,
        language_code=body.language_code,
        header_type=body.header_type,
        header_text=body.header_text,
        header_media_handle=header_media_handle,
        body_text=body.body_text,
        body_variable_count=body_variable_count,
        footer_text=body.footer_text,
        buttons=[b.model_dump() for b in body.buttons],
    )

    try:
        meta_template_id, meta_status = await MetaTemplateGateway().create_template(waba, template)
    except TemplateGatewayError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    await MessageTemplateRepository(session).set_meta_submission_result(
        template, meta_template_id=meta_template_id, status=meta_status
    )
    await session.commit()
    return MessageTemplateOut.model_validate(template)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID, tenant: CurrentTenant, session: DbSession
) -> None:
    template = await MessageTemplateRepository(session).get(tenant, template_id)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")

    if template.meta_template_id:
        waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
        if waba is not None:
            try:
                await MetaTemplateGateway().delete_template(waba, template.meta_template_id)
            except TemplateGatewayError as exc:
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    await MessageTemplateRepository(session).delete(tenant, template_id)
    await session.commit()


@router.get("", response_model=list[CampaignOut])
async def list_campaigns(tenant: CurrentTenant, session: DbSession) -> list[CampaignOut]:
    campaigns = await CampaignRepository(session).list(tenant)
    return [CampaignOut.model_validate(c) for c in campaigns]


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign_endpoint(
    body: CampaignCreate,
    tenant: CurrentTenant,
    staff_user_id: CurrentStaffUserId,
    session: DbSession,
) -> CampaignOut:
    template = await MessageTemplateRepository(session).get(tenant, body.template_id)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")

    try:
        campaign = await create_campaign(
            session,
            tenant,
            name=body.name,
            template_id=body.template_id,
            audience_filter=body.audience_filter,
            scheduled_at=body.scheduled_at,
            created_by=str(staff_user_id),
        )
    except InvalidAudienceFilterError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    await session.commit()
    return CampaignOut.model_validate(campaign)


@router.get("/{campaign_id}", response_model=CampaignDetailOut)
async def get_campaign(
    campaign_id: uuid.UUID, tenant: CurrentTenant, session: DbSession
) -> CampaignDetailOut:
    campaign = await CampaignRepository(session).get(tenant, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    return await _detail_out(session, campaign)


@router.put("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: uuid.UUID, body: CampaignUpdate, tenant: CurrentTenant, session: DbSession
) -> CampaignOut:
    campaign = await CampaignRepository(session).get(tenant, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    if campaign.status != "draft":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Only a draft campaign can be edited."
        )

    if body.audience_filter is not None:
        try:
            validate_audience_filter(body.audience_filter)
        except InvalidAudienceFilterError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    updated = await CampaignRepository(session).update_fields(
        tenant,
        campaign_id,
        name=body.name,
        template_id=body.template_id,
        audience_filter=body.audience_filter,
        scheduled_at=body.scheduled_at,
    )
    await session.commit()
    assert updated is not None  # existence already checked above
    return CampaignOut.model_validate(updated)


@router.post("/{campaign_id}/schedule", response_model=CampaignOut)
async def schedule_campaign(
    campaign_id: uuid.UUID, tenant: CurrentTenant, session: DbSession
) -> CampaignOut:
    """draft -> scheduled. The template must be approved *now*, not just
    at campaign-creation time -- Meta's review can lag template
    submission, so this is checked at schedule time, when the send is
    actually about to be authorized."""
    campaign_repo = CampaignRepository(session)
    campaign = await campaign_repo.get(tenant, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    if campaign.status != "draft":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Only a draft campaign can be scheduled."
        )

    template = await MessageTemplateRepository(session).get(tenant, campaign.template_id)
    if template is None or template.meta_approval_status != "approved":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "The campaign's template must be an approved WhatsApp template before scheduling.",
        )

    await campaign_repo.set_status(campaign, "scheduled")
    await session.commit()
    return CampaignOut.model_validate(campaign)


@router.post("/{campaign_id}/cancel", response_model=CampaignOut)
async def cancel_campaign(
    campaign_id: uuid.UUID, tenant: CurrentTenant, session: DbSession
) -> CampaignOut:
    """scheduled/sending -> failed. Maps a merchant-initiated cancel onto
    the same "failed" status a genuine send failure would reach -- this
    plan's Campaign.status enum has no dedicated "cancelled" value (see
    docs/broadcast-implementation-plan.md's Assumptions). Already-`sent`
    CampaignRecipient rows are left untouched; only still-`pending` ones
    stop being picked up by the next scheduler tick, since the campaign
    itself is no longer "scheduled"/"sending"."""
    campaign_repo = CampaignRepository(session)
    campaign = await campaign_repo.get(tenant, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    if campaign.status not in ("scheduled", "sending"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Only a scheduled or sending campaign can be cancelled.",
        )

    await campaign_repo.set_status(campaign, "failed")
    await session.commit()
    return CampaignOut.model_validate(campaign)
