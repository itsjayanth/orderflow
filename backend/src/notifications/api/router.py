from fastapi import APIRouter, HTTPException, status

from notifications.adapters.repository import NotificationTemplateRepository
from notifications.api.schemas import NotificationTemplateOut, NotificationTemplateUpdate
from notifications.domain.models import DEFAULT_MESSAGES, NOTIFICATION_KINDS, NotificationTemplate
from shared.deps import CurrentTenant, DbSession

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _to_out(kind: str, template: NotificationTemplate | None) -> NotificationTemplateOut:
    if template is None:
        return NotificationTemplateOut(
            notification_kind=kind,
            template_name="",
            language_code="en",
            body=DEFAULT_MESSAGES[kind],
            is_active=False,
            is_configured=False,
        )
    return NotificationTemplateOut(
        notification_kind=kind,
        template_name=template.template_name,
        language_code=template.language_code,
        body=template.body,
        is_active=template.is_active,
        is_configured=True,
    )


@router.get("/templates", response_model=list[NotificationTemplateOut])
async def list_templates(
    tenant: CurrentTenant, session: DbSession
) -> list[NotificationTemplateOut]:
    templates = await NotificationTemplateRepository(session).list(tenant)
    saved = {t.notification_kind: t for t in templates}
    return [_to_out(kind, saved.get(kind)) for kind in NOTIFICATION_KINDS]


@router.put("/templates/{notification_kind}", response_model=NotificationTemplateOut)
async def update_template(
    notification_kind: str,
    body: NotificationTemplateUpdate,
    tenant: CurrentTenant,
    session: DbSession,
) -> NotificationTemplateOut:
    if notification_kind not in NOTIFICATION_KINDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown notification kind")

    template = await NotificationTemplateRepository(session).upsert(
        tenant,
        notification_kind,
        template_name=body.template_name,
        language_code=body.language_code,
        body=body.body,
        is_active=body.is_active,
    )
    await session.commit()
    return _to_out(notification_kind, template)
