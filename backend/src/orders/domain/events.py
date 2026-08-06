import uuid
from collections import defaultdict
from collections.abc import Callable
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


Handler = Callable[[OrderEvent], None]

# Dead simple in-process pub-sub -- no message broker needed at this scale
# (TECH_STACK.md). Producers (Order Service) don't know who's listening;
# Notification Service (Phase 7) and, later, a Phase 2 POS Sync Service
# subscribe without Order Service changing.
_subscribers: dict[type[OrderEvent], list[Handler]] = defaultdict(list)


def subscribe(event_type: type[OrderEvent], handler: Handler) -> None:
    _subscribers[event_type].append(handler)


def publish(event: OrderEvent) -> None:
    for handler in _subscribers[type(event)]:
        handler(event)
