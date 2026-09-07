"""Shared `slowapi.Limiter` instance.

Defined in its own module (rather than on `app.py`) so that individual
routers can import it directly to apply `@limiter.limit(...)` decorators
without creating an import cycle back through `app.py` (which itself
imports every router). `app.py` imports this same instance and wires it up
as `app.state.limiter` plus the `SlowAPIMiddleware`/exception handler.

IP-keyed (`get_remote_address`), in-memory storage -- see app.py's comment
at the wiring site for the reasoning and the multi-process caveat.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
