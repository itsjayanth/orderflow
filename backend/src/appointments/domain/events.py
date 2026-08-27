import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppointmentEvent:
    appointment_id: uuid.UUID
    merchant_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class AppointmentConfirmed(AppointmentEvent):
    pass


@dataclass(frozen=True, slots=True)
class AppointmentCompleted(AppointmentEvent):
    pass


@dataclass(frozen=True, slots=True)
class AppointmentCancelled(AppointmentEvent):
    pass


Handler = Callable[[AppointmentEvent], Awaitable[None]]

# Dead simple in-process pub-sub -- its own module-level subscriber table,
# entirely separate from orders/domain/events.py's, so this feature stays
# cleanly independent of the Order domain (per the product spec). Producers
# (Appointment dashboard API) don't know who's listening; notifications/
# wiring.py subscribes without this module changing.
_subscribers: dict[type[AppointmentEvent], list[Handler]] = defaultdict(list)


def subscribe(event_type: type[AppointmentEvent], handler: Handler) -> None:
    _subscribers[event_type].append(handler)


async def publish(event: AppointmentEvent) -> None:
    for handler in _subscribers[type(event)]:
        await handler(event)
