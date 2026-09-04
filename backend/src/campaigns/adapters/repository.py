import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campaigns.domain.models import MessageTemplate
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
