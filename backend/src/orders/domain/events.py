import uuid
from dataclasses import dataclass

from shared.events import EventBus
from shared.events import Handler as _Handler


@dataclass(frozen=True, slots=True)
class OrderEvent:
    order_id: uuid.UUID
    merchant_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class OrderPaid(OrderEvent):
    pass


@dataclass(frozen=True, slots=True)
class OrderConfirmedCOD(OrderEvent):
    pass


@dataclass(frozen=True, slots=True)
class OrderProcessing(OrderEvent):
    pass


@dataclass(frozen=True, slots=True)
class OrderReady(OrderEvent):
    pass


@dataclass(frozen=True, slots=True)
class OrderCompleted(OrderEvent):
    pass


type Handler = _Handler[OrderEvent]

# Dead simple in-process pub-sub -- no message broker needed at this scale
# (TECH_STACK.md). Producers (Order Service) don't know who's listening;
# Notification Service (Phase 7) and, later, a Phase 2 POS Sync Service
# subscribe without Order Service changing. Handlers are async (sending a
# WhatsApp message is an HTTP call) and are awaited in registration order,
# synchronously with the publishing request -- there's no queue or retry
# at this scale (TECH_STACK.md), so a slow/failing notification is a
# logged no-op (see notifications/adapters/whatsapp_channel.py), not
# something that blocks or fails the request that published the event.
#
# The pub-sub mechanism itself lives in shared/events.py (generic, reused
# by appointments/domain/events.py); this module's bus instance is its own,
# independent subscriber table -- events published here are never visible
# to any other module's subscribers.
_bus: EventBus[OrderEvent] = EventBus()


def subscribe(event_type: type[OrderEvent], handler: Handler) -> None:
    _bus.subscribe(event_type, handler)


async def publish(event: OrderEvent) -> None:
    await _bus.publish(event)
