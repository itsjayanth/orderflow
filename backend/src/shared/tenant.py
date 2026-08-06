import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Carries the resolved merchant_id for a single request/webhook.

    Every tenant-scoped repository method takes this as its first argument
    (ARCHITECTURE.md Section 2) so cross-tenant access is an interface-level
    mistake, not something only code review catches.
    """

    merchant_id: uuid.UUID
