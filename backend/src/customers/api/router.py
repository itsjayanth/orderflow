import uuid

from fastapi import APIRouter, HTTPException, status

from customers.adapters.repository import AddressRepository, CustomerRepository
from customers.api.schemas import AddressOut, CustomerOut, CustomerWithAddressesOut
from shared.deps import CurrentTenant, DbSession

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.get("", response_model=list[CustomerOut])
async def list_customers(tenant: CurrentTenant, session: DbSession) -> list[CustomerOut]:
    customers = await CustomerRepository(session).list(tenant)
    return [CustomerOut.model_validate(customer) for customer in customers]


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
