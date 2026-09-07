import uuid
from dataclasses import dataclass

from shared.events import EventBus
from shared.events import Handler as _Handler


@dataclass(frozen=True, slots=True)
class AppointmentEvent:
    appointment_id: uuid.UUID
    merchant_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class AppointmentRequested(AppointmentEvent):
    pass


@dataclass(frozen=True, slots=True)
class AppointmentConfirmed(AppointmentEvent):
    pass


@dataclass(frozen=True, slots=True)
class AppointmentCompleted(AppointmentEvent):
    pass


@dataclass(frozen=True, slots=True)
class AppointmentCancelled(AppointmentEvent):
    pass


type Handler = _Handler[AppointmentEvent]

# Dead simple in-process pub-sub -- its own module-level subscriber table,
# entirely separate from orders/domain/events.py's, so this feature stays
# cleanly independent of the Order domain (per the product spec). Producers
# (Appointment dashboard API) don't know who's listening; notifications/
# wiring.py subscribes without this module changing.
#
# The pub-sub mechanism itself lives in shared/events.py (generic, reused
# by orders/domain/events.py); this module's bus instance is its own,
# independent subscriber table -- events published here are never visible
# to any other module's subscribers.
_bus: EventBus[AppointmentEvent] = EventBus()


def subscribe(event_type: type[AppointmentEvent], handler: Handler) -> None:
    _bus.subscribe(event_type, handler)


async def publish(event: AppointmentEvent) -> None:
    await _bus.publish(event)
