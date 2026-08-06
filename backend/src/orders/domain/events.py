import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


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
class OrderReady(OrderEvent):
    pass


@dataclass(frozen=True, slots=True)
class OrderCompleted(OrderEvent):
    pass


Handler = Callable[[OrderEvent], Awaitable[None]]

# Dead simple in-process pub-sub -- no message broker needed at this scale
# (TECH_STACK.md). Producers (Order Service) don't know who's listening;
# Notification Service (Phase 7) and, later, a Phase 2 POS Sync Service
# subscribe without Order Service changing. Handlers are async (sending a
# WhatsApp message is an HTTP call) and are awaited in registration order,
# synchronously with the publishing request -- there's no queue or retry
# at this scale (TECH_STACK.md), so a slow/failing notification is a
# logged no-op (see notifications/adapters/whatsapp_channel.py), not
# something that blocks or fails the request that published the event.
_subscribers: dict[type[OrderEvent], list[Handler]] = defaultdict(list)


def subscribe(event_type: type[OrderEvent], handler: Handler) -> None:
    _subscribers[event_type].append(handler)


async def publish(event: OrderEvent) -> None:
    for handler in _subscribers[type(event)]:
        await handler(event)
