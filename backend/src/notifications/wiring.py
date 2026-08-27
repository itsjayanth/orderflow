from appointments.domain.events import (
    AppointmentCancelled,
    AppointmentConfirmed,
    AppointmentEvent,
)
from appointments.domain.events import (
    subscribe as subscribe_appointment_event,
)
from conversation.adapters.whatsapp_client import GraphApiWhatsAppSender
from notifications.adapters.whatsapp_channel import WhatsAppNotificationChannel
from notifications.domain.channel import NotificationChannel
from orders.domain.events import (
    OrderCompleted,
    OrderConfirmedCOD,
    OrderEvent,
    OrderPaid,
    OrderPreparing,
    OrderReady,
    subscribe,
)

# A mutable module-level reference, not baked into the subscribed closures
# below -- lets tests swap in a fake channel (set_notification_channel)
# without re-subscribing, since register_notification_handlers only ever
# runs once (subscriptions accumulate otherwise).
_channel: NotificationChannel = WhatsAppNotificationChannel(GraphApiWhatsAppSender())
_registered = False


def set_notification_channel(channel: NotificationChannel) -> None:
    global _channel
    _channel = channel


def get_notification_channel() -> NotificationChannel:
    return _channel


async def _on_order_confirmed(event: OrderEvent) -> None:
    await _channel.notify_order_confirmed(merchant_id=event.merchant_id, order_id=event.order_id)


async def _on_order_preparing(event: OrderEvent) -> None:
    await _channel.notify_order_preparing(merchant_id=event.merchant_id, order_id=event.order_id)


async def _on_order_ready(event: OrderEvent) -> None:
    await _channel.notify_order_ready(merchant_id=event.merchant_id, order_id=event.order_id)


async def _on_order_completed(event: OrderEvent) -> None:
    await _channel.notify_order_completed(merchant_id=event.merchant_id, order_id=event.order_id)


async def _on_appointment_confirmed(event: AppointmentEvent) -> None:
    await _channel.notify_appointment_confirmed(
        merchant_id=event.merchant_id, appointment_id=event.appointment_id
    )


async def _on_appointment_cancelled(event: AppointmentEvent) -> None:
    await _channel.notify_appointment_cancelled(
        merchant_id=event.merchant_id, appointment_id=event.appointment_id
    )


def register_notification_handlers() -> None:
    """Called once at app import time (app.py, module level -- not inside
    the lifespan context manager, which doesn't run under the ASGITransport
    tests use). Idempotent so an accidental second call doesn't double-
    subscribe and send every notification twice."""
    global _registered
    if _registered:
        return
    subscribe(OrderPaid, _on_order_confirmed)
    subscribe(OrderConfirmedCOD, _on_order_confirmed)
    subscribe(OrderPreparing, _on_order_preparing)
    subscribe(OrderReady, _on_order_ready)
    subscribe(OrderCompleted, _on_order_completed)
    # A second, separate pub-sub system from orders' -- see
    # appointments/domain/events.py.
    subscribe_appointment_event(AppointmentConfirmed, _on_appointment_confirmed)
    subscribe_appointment_event(AppointmentCancelled, _on_appointment_cancelled)
    _registered = True
