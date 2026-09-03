import datetime
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from appointment_flow.domain.booking import PastDateError, perform_booking
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from identity.domain.models import Merchant
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from shared.encryption import encrypt
from shared.tenant import TenantContext

# A fixed calendar date goes stale the moment the wall clock crosses it --
# perform_booking's past-date check would then reject every test in this
# file. Compute a date that's always safely in the future instead.
_FUTURE_DATE = datetime.date.today() + datetime.timedelta(days=30)
_FUTURE_DATE_ISO = _FUTURE_DATE.isoformat()


async def _make_tenant(
    db_session: AsyncSession, *, appointment_enabled: bool = True
) -> tuple[Merchant, TenantContext]:
    merchant = await MerchantRepository(db_session).create(
        business_name="Public Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    merchant.appointment_enabled = appointment_enabled
    await db_session.commit()
    return merchant, TenantContext(merchant_id=merchant.merchant_id)


async def _register(client: AsyncClient, owner_contact: str = "owner@example.com") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Public Business",
            "owner_name": "Jane Owner",
            "owner_contact": owner_contact,
            "password": "correct-horse-battery-staple",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _tenant_for(client: AsyncClient, tokens: dict) -> TenantContext:
    me = await client.get("/api/v1/auth/me", headers=_auth_headers(tokens))
    assert me.status_code == 200
    return TenantContext(merchant_id=uuid.UUID(me.json()["merchant"]["merchant_id"]))


async def _connect_whatsapp(
    db_session: AsyncSession, tenant: TenantContext, display_phone_number: str
) -> None:
    await WhatsAppBusinessAccountRepository(db_session).upsert(
        tenant,
        phone_number_id="PNID1",
        access_token_encrypted=encrypt("dummy-token"),
        display_phone_number=display_phone_number,
    )
    await db_session.commit()


async def _select_appointment_vertical(client: AsyncClient, tokens: dict) -> None:
    response = await client.put(
        "/api/v1/onboarding/verticals",
        json={"restaurant_enabled": False, "appointment_enabled": True},
        headers=_auth_headers(tokens),
    )
    assert response.status_code == 200


# --- perform_booking ---------------------------------------------------


async def test_perform_booking_creates_customer_and_appointment(
    db_session: AsyncSession,
) -> None:
    merchant, tenant = await _make_tenant(db_session)

    result = await perform_booking(
        db_session,
        tenant,
        merchant,
        customer_whatsapp_number="+919876543210",
        customer_display_name="Asha",
        name="Asha Rao",
        email="asha@example.com",
        appointment_date=_FUTURE_DATE,
        start_time=datetime.time(18, 0),
    )

    assert result.appointment.status == "requested"
    assert result.appointment.name == "Asha Rao"
    assert result.appointment.appointment_number == 1

    customer = await CustomerRepository(db_session).get_by_whatsapp_number(
        tenant, "+919876543210"
    )
    assert customer is not None
    assert customer.customer_id == result.appointment.customer_id


async def test_perform_booking_reuses_existing_customer(db_session: AsyncSession) -> None:
    merchant, tenant = await _make_tenant(db_session)
    existing = await CustomerRepository(db_session).find_or_create(
        tenant, "+919876543210", display_name="Asha"
    )
    await db_session.commit()

    result = await perform_booking(
        db_session,
        tenant,
        merchant,
        customer_whatsapp_number="+919876543210",
        customer_display_name="Asha",
        name="Asha Rao",
        email="asha@example.com",
        appointment_date=_FUTURE_DATE,
        start_time=datetime.time(18, 0),
    )

    assert result.appointment.customer_id == existing.customer_id


async def test_perform_booking_rejects_past_date(db_session: AsyncSession) -> None:
    merchant, tenant = await _make_tenant(db_session)

    with pytest.raises(PastDateError):
        await perform_booking(
            db_session,
            tenant,
            merchant,
            customer_whatsapp_number="+919876543210",
            customer_display_name="Asha",
            name="Asha Rao",
            email="asha@example.com",
            appointment_date=datetime.date(2020, 1, 1),
            start_time=datetime.time(18, 0),
        )


# --- public appointment-flow router --------------------------------------


async def test_appointment_flow_info_requires_no_auth(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _select_appointment_vertical(client, tokens)

    response = await client.get(f"/api/v1/appointment-flow/{tenant.merchant_id}/info")

    assert response.status_code == 200
    assert response.json()["business_name"] == "Public Business"


async def test_appointment_flow_info_exposes_merchant_whatsapp_number(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _select_appointment_vertical(client, tokens)
    await _connect_whatsapp(db_session, tenant, "+91 90000 00000")

    response = await client.get(f"/api/v1/appointment-flow/{tenant.merchant_id}/info")

    assert response.status_code == 200
    # The dialable display number (as Meta returns it, "+" and spaces
    # included), not the opaque phone_number_id -- the booking webview
    # strips non-digits to build the wa.me link back to the chat.
    assert response.json()["merchant_whatsapp_number"] == "+91 90000 00000"


async def test_appointment_flow_info_whatsapp_number_null_without_waba(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _select_appointment_vertical(client, tokens)

    response = await client.get(f"/api/v1/appointment-flow/{tenant.merchant_id}/info")

    assert response.status_code == 200
    assert response.json()["merchant_whatsapp_number"] is None


async def test_appointment_flow_info_404_when_not_appointment_vertical(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)

    response = await client.get(f"/api/v1/appointment-flow/{tenant.merchant_id}/info")

    assert response.status_code == 404


async def test_appointment_flow_info_404_for_unknown_merchant(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/appointment-flow/{uuid.uuid4()}/info")

    assert response.status_code == 404


# --- customer-lookup (prefill for the booking webview) -------------------


async def test_appointment_customer_lookup_returns_404_for_new_customer(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _select_appointment_vertical(client, tokens)

    response = await client.get(
        f"/api/v1/appointment-flow/{tenant.merchant_id}/customer-lookup",
        params={"whatsapp_number": "+919876543210"},
    )

    assert response.status_code == 404


async def test_appointment_customer_lookup_unknown_merchant_returns_404(
    client: AsyncClient,
) -> None:
    response = await client.get(
        f"/api/v1/appointment-flow/{uuid.uuid4()}/customer-lookup",
        params={"whatsapp_number": "+919876543210"},
    )

    assert response.status_code == 404


async def test_appointment_customer_lookup_returns_name_and_email_for_returning_customer(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _select_appointment_vertical(client, tokens)
    await CustomerRepository(db_session).create(
        tenant, whatsapp_number="+919876543210", display_name="Asha", email="asha@example.com"
    )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/appointment-flow/{tenant.merchant_id}/customer-lookup",
        params={"whatsapp_number": "+919876543210"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Asha"
    assert body["email"] == "asha@example.com"


async def test_appointment_customer_lookup_returns_blank_email_when_customer_never_gave_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A customer with a phone on file (e.g. from a past order) but no
    email yet -- an incomplete profile to fill once, not an error."""
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _select_appointment_vertical(client, tokens)
    await CustomerRepository(db_session).find_or_create(
        tenant, "+919876543210", display_name="Asha"
    )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/appointment-flow/{tenant.merchant_id}/customer-lookup",
        params={"whatsapp_number": "+919876543210"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Asha"
    assert body["email"] is None


async def test_appointment_customer_lookup_isolated_between_merchants(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    tenant_a = await _tenant_for(client, tokens_a)
    await _select_appointment_vertical(client, tokens_a)
    await CustomerRepository(db_session).create(
        tenant_a, whatsapp_number="+919876543210", display_name="Asha", email="asha@example.com"
    )
    await db_session.commit()

    tokens_b = await _register(client, owner_contact="owner-b@example.com")
    tenant_b = await _tenant_for(client, tokens_b)
    await _select_appointment_vertical(client, tokens_b)

    response = await client.get(
        f"/api/v1/appointment-flow/{tenant_b.merchant_id}/customer-lookup",
        params={"whatsapp_number": "+919876543210"},
    )

    assert response.status_code == 404


# --- /book: persistence + identity-resolution behavior --------------------


async def test_book_appointment_persists_edited_name_and_email_as_new_defaults(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _select_appointment_vertical(client, tokens)
    await CustomerRepository(db_session).find_or_create(
        tenant, "+919876543210", display_name="Asha"
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/appointment-flow/{tenant.merchant_id}/book",
        json={
            "customer_whatsapp_number": "+919876543210",
            "name": "Asha Rao",
            "email": "asha.rao@example.com",
            "appointment_date": _FUTURE_DATE_ISO,
            "start_time": "18:00:00",
        },
    )
    assert response.status_code == 201, response.text

    customer = await CustomerRepository(db_session).get_by_whatsapp_number(
        tenant, "+919876543210"
    )
    assert customer is not None
    assert customer.display_name == "Asha Rao"
    assert customer.email == "asha.rao@example.com"


async def test_book_appointment_request_schema_has_no_contact_phone_override_field() -> None:
    """The appointment webview has no "use a different number" concept --
    AppointmentFlowBookingRequest deliberately carries no contact-phone-
    override field the order flow's OrderingFlowCheckoutRequest has, so
    there's no field a crafted payload could even use to try."""
    from appointment_flow.api.schemas import AppointmentFlowBookingRequest

    assert "contact_phone" not in AppointmentFlowBookingRequest.model_fields


async def test_book_appointment_happy_path(client: AsyncClient, db_session: AsyncSession) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _select_appointment_vertical(client, tokens)

    response = await client.post(
        f"/api/v1/appointment-flow/{tenant.merchant_id}/book",
        json={
            "customer_whatsapp_number": "+919876543210",
            "customer_display_name": "Asha",
            "name": "Asha Rao",
            "email": "asha@example.com",
            "appointment_date": _FUTURE_DATE_ISO,
            "start_time": "18:00:00",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["appointment_number"] == 1
    assert body["status"] == "requested"

    # Shows up on the merchant's dashboard immediately.
    appointments_response = await client.get(
        "/api/v1/appointments", headers=_auth_headers(tokens)
    )
    assert len(appointments_response.json()) == 1


async def test_book_appointment_404_when_not_appointment_vertical(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)

    response = await client.post(
        f"/api/v1/appointment-flow/{tenant.merchant_id}/book",
        json={
            "customer_whatsapp_number": "+919876543210",
            "name": "Asha Rao",
            "email": "asha@example.com",
            "appointment_date": _FUTURE_DATE_ISO,
            "start_time": "18:00:00",
        },
    )

    assert response.status_code == 404


async def test_book_appointment_404_for_unknown_merchant(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/appointment-flow/{uuid.uuid4()}/book",
        json={
            "customer_whatsapp_number": "+919876543210",
            "name": "Asha Rao",
            "email": "asha@example.com",
            "appointment_date": _FUTURE_DATE_ISO,
            "start_time": "18:00:00",
        },
    )

    assert response.status_code == 404


async def test_book_appointment_past_date_returns_400(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _select_appointment_vertical(client, tokens)

    response = await client.post(
        f"/api/v1/appointment-flow/{tenant.merchant_id}/book",
        json={
            "customer_whatsapp_number": "+919876543210",
            "name": "Asha Rao",
            "email": "asha@example.com",
            "appointment_date": "2020-01-01",
            "start_time": "18:00:00",
        },
    )

    assert response.status_code == 400


async def test_book_appointment_invalid_email_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _select_appointment_vertical(client, tokens)

    response = await client.post(
        f"/api/v1/appointment-flow/{tenant.merchant_id}/book",
        json={
            "customer_whatsapp_number": "+919876543210",
            "name": "Asha Rao",
            "email": "not-an-email",
            "appointment_date": _FUTURE_DATE_ISO,
            "start_time": "18:00:00",
        },
    )

    assert response.status_code == 422


async def test_appointment_flow_isolated_between_merchants(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    tenant_a = await _tenant_for(client, tokens_a)
    await _select_appointment_vertical(client, tokens_a)

    tokens_b = await _register(client, owner_contact="owner-b@example.com")

    response = await client.post(
        f"/api/v1/appointment-flow/{tenant_a.merchant_id}/book",
        json={
            "customer_whatsapp_number": "+919876543210",
            "name": "Asha Rao",
            "email": "asha@example.com",
            "appointment_date": _FUTURE_DATE_ISO,
            "start_time": "18:00:00",
        },
    )
    assert response.status_code == 201, response.text

    # Merchant B's dashboard never sees merchant A's appointment.
    response_b = await client.get("/api/v1/appointments", headers=_auth_headers(tokens_b))
    assert response_b.json() == []
