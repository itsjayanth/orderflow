"""Generic in-process pub-sub engine.

Dead simple in-process pub-sub -- no message broker needed at this scale
(TECH_STACK.md). Handlers are async and are awaited in registration order,
synchronously with the publishing call -- there's no queue or retry at this
scale, so a slow/failing handler is the caller's problem to log and swallow,
not something this engine handles specially.

This module holds only the generic mechanism. Each domain module (e.g.
`orders/domain/events.py`, `appointments/domain/events.py`) instantiates its
own `EventBus[...]()` -- a fresh, independent subscriber table -- so events
published on one domain's bus are never visible to another domain's
subscribers.
"""

from collections import defaultdict
from collections.abc import Awaitable, Callable

type Handler[E] = Callable[[E], Awaitable[None]]


class EventBus[E]:
    """A single independent pub-sub table for events of type E (and subtypes)."""

    def __init__(self) -> None:
        self._subscribers: dict[type[E], list[Handler[E]]] = defaultdict(list)

    def subscribe(self, event_type: type[E], handler: Handler[E]) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event: E) -> None:
        for handler in self._subscribers[type(event)]:
            await handler(event)
