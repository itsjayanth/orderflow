import base64
import binascii
import uuid

from fastapi import APIRouter, HTTPException, status

from campaigns.adapters.media_upload import MediaUploadError, upload_header_image
from campaigns.adapters.repository import MessageTemplateRepository
from campaigns.adapters.template_gateway import MetaTemplateGateway, TemplateGatewayError
from campaigns.api.schemas import MessageTemplateCreate, MessageTemplateOut
from campaigns.domain.template_validation import InvalidTemplateError, normalize_template_name
from campaigns.domain.template_validation import validate_template as validate_template_fields
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from shared.deps import CurrentTenant, DbSession

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


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
