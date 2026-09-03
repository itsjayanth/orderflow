import uuid

from appointments.adapters.repository import AppointmentRepository
from appointments.adapters.scheduling_repository import AppointmentServiceRepository
from conversation.adapters.whatsapp_client import WhatsAppSender
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from notifications.adapters.repository import NotificationTemplateRepository
from notifications.domain.models import DEFAULT_MESSAGES
from notifications.domain.rendering import render_template
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from orders.adapters.repository import OrderRepository
from shared.config import get_settings
from shared.db import SessionFactory
from shared.encryption import decrypt
from shared.tenant import TenantContext


class WhatsAppNotificationChannel:
    """Each call opens its own session (like shared/scheduler.py's sweep
    job) -- notification handlers run after the triggering request has
    already committed, so there's nothing to share a transaction with."""

    def __init__(self, sender: WhatsAppSender) -> None:
        self._sender = sender

    async def _send(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID, kind: str) -> bool:
        tenant = TenantContext(merchant_id=merchant_id)
        async with SessionFactory() as session:
            waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
            if waba is None or waba.phone_number_id is None or waba.access_token_encrypted is None:
                return False

            order = await OrderRepository(session).get(tenant, order_id)
            if order is None:
                return False

            customer = await CustomerRepository(session).get(tenant, order.customer_id)
            if customer is None:
                return False

            merchant = await MerchantRepository(session).get(tenant.merchant_id)

            items = "\n".join(
                f"{item.quantity}x {item.name_snapshot} - {order.currency} {item.line_total}"
                for item in order.items
            )
            context = {
                "business_name": merchant.business_name if merchant else "",
                "customer_name": customer.display_name or "",
                "order_id": str(order.order_id),
                "order_number": f"{order.order_number:04d}",
                "total": str(order.total),
                "currency": order.currency,
                "items": items,
            }
            template = await NotificationTemplateRepository(session).get(tenant, kind)
            template_body = (
                template.body
                if template is not None and template.is_active
                else DEFAULT_MESSAGES[kind]
            )
            message = render_template(template_body, context)

            return await self._sender.send_text(
                phone_number_id=waba.phone_number_id,
                access_token=decrypt(waba.access_token_encrypted),
                to=customer.whatsapp_number,
                body=message,
            )

    async def notify_order_confirmed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return await self._send(merchant_id=merchant_id, order_id=order_id, kind="order_confirmed")

    async def notify_order_processing(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return await self._send(merchant_id=merchant_id, order_id=order_id, kind="order_processing")

    async def notify_order_ready(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return await self._send(merchant_id=merchant_id, order_id=order_id, kind="order_ready")

    async def notify_order_completed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return await self._send(merchant_id=merchant_id, order_id=order_id, kind="order_completed")

    async def _send_appointment(
        self, *, merchant_id: uuid.UUID, appointment_id: uuid.UUID, kind: str
    ) -> bool:
        """Mirrors _send exactly, but for the Appointment domain -- kept as
        a separate method (rather than generalizing _send) so this class
        stays a straightforward, easy-to-follow one-method-per-domain
        pair, same as the rest of this codebase's style."""
        tenant = TenantContext(merchant_id=merchant_id)
        async with SessionFactory() as session:
            waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
            if waba is None or waba.phone_number_id is None or waba.access_token_encrypted is None:
                return False

            appointment = await AppointmentRepository(session).get(tenant, appointment_id)
            if appointment is None:
                return False

            merchant = await MerchantRepository(session).get(tenant.merchant_id)

            # Only "appointment_requested"'s default template actually uses
            # service_line, but it costs nothing to include it in every
            # appointment context -- render_template just ignores unused
            # keys, same as appointment_id/notes already do for kinds that
            # don't reference them.
            service_line = ""
            if appointment.service_id is not None:
                service = await AppointmentServiceRepository(session).get(
                    tenant, appointment.service_id
                )
                if service is not None:
                    service_line = f"{service.name} — "

            context = {
                "business_name": merchant.business_name if merchant else "",
                "customer_name": appointment.customer.display_name or "",
                "appointment_id": str(appointment.appointment_id),
                "appointment_number": f"{appointment.appointment_number:04d}",
                "appointment_date": str(appointment.appointment_date),
                "appointment_time": str(appointment.start_time),
                "service_line": service_line,
                "notes": appointment.notes or "",
            }
            template = await NotificationTemplateRepository(session).get(tenant, kind)
            template_body = (
                template.body
                if template is not None and template.is_active
                else DEFAULT_MESSAGES[kind]
            )
            message = render_template(template_body, context)

            return await self._sender.send_text(
                phone_number_id=waba.phone_number_id,
                access_token=decrypt(waba.access_token_encrypted),
                to=appointment.customer.whatsapp_number,
                body=message,
            )

    async def notify_appointment_requested(
        self, *, merchant_id: uuid.UUID, appointment_id: uuid.UUID
    ) -> bool:
        return await self._send_appointment(
            merchant_id=merchant_id, appointment_id=appointment_id, kind="appointment_requested"
        )

    async def notify_appointment_confirmed(
        self, *, merchant_id: uuid.UUID, appointment_id: uuid.UUID
    ) -> bool:
        return await self._send_appointment(
            merchant_id=merchant_id, appointment_id=appointment_id, kind="appointment_confirmed"
        )

    async def notify_appointment_cancelled(
        self, *, merchant_id: uuid.UUID, appointment_id: uuid.UUID
    ) -> bool:
        return await self._send_appointment(
            merchant_id=merchant_id, appointment_id=appointment_id, kind="appointment_cancelled"
        )

    async def notify_appointment_reminder(
        self, *, merchant_id: uuid.UUID, appointment_id: uuid.UUID, kind: str | None
    ) -> bool:
        """Distinct from _send_appointment above -- a reminder fires
        minutes/hours after the triggering (confirmed) transition,
        genuinely outside the customer's 24h WhatsApp session window, so
        it must go out as a Meta-approved `type: template` send
        (send_template_message) with positional body params, not the
        freeform send_text + our-own-{{var}}-rendering _send_appointment
        uses for the immediate confirmed/cancelled notifications.

        `kind` is "appointment_reminder_60m" or "appointment_reminder_30m"
        for a merchant's two named offsets, or None for any other minute
        offset a merchant configures (shared/scheduler.py's
        _REMINDER_KIND_BY_OFFSET_MINUTES only names those two -- there's
        no bespoke per-offset template for an arbitrary value, so it
        isn't one of NOTIFICATION_KINDS at all). Which Meta template
        actually gets sent: when `kind` is given, the merchant's own
        NotificationTemplate row for that kind if they've configured and
        activated one (its template_name/language_code -- NOT its body,
        which for these two kinds is preview-only, see
        notifications/domain/models.py); otherwise (kind is None, or no
        such row/it's inactive) the single global env-configured reminder
        template (whatsapp_appointment_reminder_template_name) as the
        shared default every offset falls back to. Returns False (no send
        attempted) when neither resolves to a template name -- same
        "unset = safe no-op" convention as every other optional Meta
        config in this codebase."""
        tenant = TenantContext(merchant_id=merchant_id)
        async with SessionFactory() as session:
            waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
            if waba is None or waba.phone_number_id is None or waba.access_token_encrypted is None:
                return False

            appointment = await AppointmentRepository(session).get(tenant, appointment_id)
            if appointment is None:
                return False

            settings = get_settings()
            template = (
                await NotificationTemplateRepository(session).get(tenant, kind)
                if kind is not None
                else None
            )
            template_name: str | None
            if template is not None and template.is_active:
                template_name = template.template_name
                language_code = template.language_code
            else:
                template_name = settings.whatsapp_appointment_reminder_template_name
                language_code = settings.whatsapp_appointment_reminder_language_code
            if not template_name:
                return False

            merchant = await MerchantRepository(session).get(tenant.merchant_id)
            body_params = [
                merchant.business_name if merchant else "",
                f"{appointment.appointment_number:04d}",
                appointment.appointment_date.strftime("%a, %d %b"),
                appointment.start_time.strftime("%I:%M %p").lstrip("0"),
            ]

            return await self._sender.send_template_message(
                phone_number_id=waba.phone_number_id,
                access_token=decrypt(waba.access_token_encrypted),
                to=appointment.customer.whatsapp_number,
                template_name=template_name,
                language_code=language_code,
                body_params=body_params,
            )
