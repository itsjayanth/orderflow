import uuid

from fastapi import APIRouter, HTTPException, status

from customers.adapters.repository import (
    AddressRepository,
    CustomerRepository,
    CustomerWhatsAppNumberConflictError,
)
from customers.api.schemas import (
    AddressOut,
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
    CustomerWithAddressesOut,
)
from shared.deps import CurrentTenant, DbSession

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.get("", response_model=list[CustomerOut])
async def list_customers(
    tenant: CurrentTenant, session: DbSession, include_inactive: bool = False
) -> list[CustomerOut]:
    customers = await CustomerRepository(session).list(tenant, include_inactive=include_inactive)
    return [CustomerOut.model_validate(customer) for customer in customers]


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate, tenant: CurrentTenant, session: DbSession
) -> CustomerOut:
    try:
        customer = await CustomerRepository(session).create(
            tenant,
            whatsapp_number=body.whatsapp_number,
            display_name=body.display_name,
            default_contact_phone=body.default_contact_phone,
            email=body.email,
        )
    except CustomerWhatsAppNumberConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A customer with this WhatsApp number already exists"
        ) from exc
    await session.commit()
    return CustomerOut.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerOut)
async def update_customer(
    customer_id: uuid.UUID, body: CustomerUpdate, tenant: CurrentTenant, session: DbSession
) -> CustomerOut:
    customer = await CustomerRepository(session).update(
        tenant, customer_id, **body.model_dump(exclude_unset=True)
    )
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    await session.commit()
    return CustomerOut.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerWithAddressesOut)
async def get_customer(
    customer_id: uuid.UUID, tenant: CurrentTenant, session: DbSession
) -> CustomerWithAddressesOut:
    customer = await CustomerRepository(session).get(tenant, customer_id)
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")

    addresses = await AddressRepository(session).list_for_customer(tenant, customer_id)
    return CustomerWithAddressesOut(
        **CustomerOut.model_validate(customer).model_dump(),
        addresses=[AddressOut.model_validate(a) for a in addresses],
    )
