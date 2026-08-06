from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from notifications.domain.models import NotificationTemplate
from shared.tenant import TenantContext


class NotificationTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, tenant: TenantContext) -> list[NotificationTemplate]:
        result = await self._session.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.merchant_id == tenant.merchant_id
            )
        )
        return list(result.scalars().all())

    async def get(
        self, tenant: TenantContext, notification_kind: str
    ) -> NotificationTemplate | None:
        result = await self._session.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.merchant_id == tenant.merchant_id,
                NotificationTemplate.notification_kind == notification_kind,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        tenant: TenantContext,
        notification_kind: str,
        *,
        template_name: str,
        language_code: str,
        body: str,
        is_active: bool,
    ) -> NotificationTemplate:
        template = await self.get(tenant, notification_kind)
        if template is None:
            template = NotificationTemplate(
                merchant_id=tenant.merchant_id, notification_kind=notification_kind
            )
            self._session.add(template)

        template.template_name = template_name
        template.language_code = language_code
        template.body = body
        template.is_active = is_active

        await self._session.flush()
        return template
