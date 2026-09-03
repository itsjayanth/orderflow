import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from customers.adapters.repository import AddressRepository, CustomerRepository
from customers.domain.models import Address, Customer
from customers.domain.phone import normalize_whatsapp_id
from shared.tenant import TenantContext

logger = logging.getLogger(__name__)

# Both callers (the native Flow's encrypted round trip, the browser-link
# webview's DB lookup) are in-process DB reads with no external network
# hop, so this is generous headroom for a slow query, not a real timeout
# budget -- its only job is to guarantee a lookup can never hang the
# customer's flow indefinitely.
_LOOKUP_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class ResolvedCustomer:
    customer: Customer
    address: Address | None


async def resolve_customer_by_whatsapp_id(
    session: AsyncSession,
    tenant: TenantContext,
    raw_whatsapp_id: object,
    *,
    include_address: bool = False,
) -> ResolvedCustomer | None:
    """The one shared identity-resolution entrypoint for both the order and
    appointment flows (native WhatsApp Flow and browser-link webview
    alike): given whatever server-derived value each surface has for "who
    is this" (a native Flow's flow_token, a webview's `?wa=` query param),
    normalizes it and looks up a saved Customer row. Returns None -- never
    raises -- for a malformed/missing id, a customer nobody's seen before,
    or a lookup that fails/times out, so every caller's fallback is
    uniformly "render empty fields," matching this feature's "never block
    the flow" requirement. Callers must not pass a client-editable phone
    field into raw_whatsapp_id -- only a value the server itself derived
    (flow_token, or the `wa` query param a WhatsApp CTA link embeds) --
    since this function's result drives what gets shown back as "your
    saved details," and trusting an arbitrary client value here would let
    one customer read another's."""
    whatsapp_id = normalize_whatsapp_id(raw_whatsapp_id)
    if whatsapp_id is None:
        logger.info(
            "identity_resolution: no usable whatsapp id for merchant %s, falling back to "
            "empty fields",
            tenant.merchant_id,
        )
        return None

    try:
        async with asyncio.timeout(_LOOKUP_TIMEOUT_SECONDS):
            customer = await CustomerRepository(session).get_by_whatsapp_number(
                tenant, whatsapp_id
            )
    except TimeoutError:
        logger.warning(
            "identity_resolution: customer lookup timed out for merchant %s, falling back",
            tenant.merchant_id,
        )
        return None
    except Exception:
        # Deliberately broad: a lookup failure here must never surface as a
        # broken checkout/booking screen -- see this feature's "fall back
        # gracefully, never block the flow" requirement. The exception is
        # still logged (with a traceback) so a real, recurring failure is
        # visible in logs rather than silently swallowed forever.
        logger.exception(
            "identity_resolution: customer lookup failed for merchant %s, falling back",
            tenant.merchant_id,
        )
        return None

    if customer is None:
        # New customer -- the normal case, not an error. Nothing to log
        # beyond this: no PII, no customer_id to report either.
        logger.info(
            "identity_resolution: no saved customer on file for merchant %s", tenant.merchant_id
        )
        return None

    address = None
    if include_address:
        try:
            async with asyncio.timeout(_LOOKUP_TIMEOUT_SECONDS):
                address = await AddressRepository(session).get_primary_for_customer(
                    tenant, customer.customer_id
                )
        except TimeoutError:
            logger.warning(
                "identity_resolution: address lookup timed out for customer %s, "
                "continuing without a saved address",
                customer.customer_id,
            )
        except Exception:
            logger.exception(
                "identity_resolution: address lookup failed for customer %s, "
                "continuing without a saved address",
                customer.customer_id,
            )

    # Audit trail for what got auto-filled, without ever putting the name/
    # phone/address/email themselves in the log line -- customer_id is an
    # internal UUID, not customer-facing PII.
    logger.info(
        "identity_resolution: resolved customer_id=%s for merchant %s (autofill available, "
        "has_address=%s)",
        customer.customer_id,
        tenant.merchant_id,
        address is not None,
    )
    return ResolvedCustomer(customer=customer, address=address)
