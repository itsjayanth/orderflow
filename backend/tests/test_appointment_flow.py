import datetime
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from appointment_flow.domain.booking import PastDateError, perform_booking
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from shared.tenant import TenantContext


async def _make_tenant(
    db_session: AsyncSession, *, appointment_booking_enabled: bool = True
) -> TenantContext:
    merchant = await MerchantRepository(db_session).create(
        business_name="Public Kitchen", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    merchant.appointment_booking_enabled = appointment_booking_enabled
    await db_session.commit()
    return TenantContext(merchant_id=merchant.merchant_id)


async def _register(client: AsyncClient, owner_contact: str = "owner@example.com") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Public Kitchen",
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


async def _enable_appointment_booking(client: AsyncClient, tokens: dict) -> None:
    response = await client.patch(
        "/api/v1/auth/appointment-settings", json={"enabled": True}, headers=_auth_headers(tokens)
    )
    assert response.status_code == 200


# --- perform_booking ---------------------------------------------------


async def test_perform_booking_creates_customer_and_appointment(
    db_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(db_session)

    result = await perform_booking(
        db_session,
        tenant,
        customer_whatsapp_number="+919876543210",
        customer_display_name="Asha",
        name="Asha Rao",
        email="asha@example.com",
        appointment_date=datetime.date(2026, 9, 1),
        appointment_time=datetime.time(18, 0),
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
    tenant = await _make_tenant(db_session)
    existing = await CustomerRepository(db_session).find_or_create(
        tenant, "+919876543210", display_name="Asha"
    )
    await db_session.commit()

    result = await perform_booking(
        db_session,
        tenant,
        customer_whatsapp_number="+919876543210",
        customer_display_name="Asha",
        name="Asha Rao",
        email="asha@example.com",
        appointment_date=datetime.date(2026, 9, 1),
        appointment_time=datetime.time(18, 0),
    )

    assert result.appointment.customer_id == existing.customer_id


async def test_perform_booking_rejects_past_date(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)

    with pytest.raises(PastDateError):
        await perform_booking(
            db_session,
            tenant,
            customer_whatsapp_number="+919876543210",
            customer_display_name="Asha",
            name="Asha Rao",
            email="asha@example.com",
            appointment_date=datetime.date(2020, 1, 1),
            appointment_time=datetime.time(18, 0),
        )


# --- public appointment-flow router --------------------------------------


async def test_appointment_flow_info_requires_no_auth(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _enable_appointment_booking(client, tokens)

    response = await client.get(f"/api/v1/appointment-flow/{tenant.merchant_id}/info")

    assert response.status_code == 200
    assert response.json()["business_name"] == "Public Kitchen"


async def test_appointment_flow_info_404_when_toggle_off(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)

    response = await client.get(f"/api/v1/appointment-flow/{tenant.merchant_id}/info")

    assert response.status_code == 404


async def test_appointment_flow_info_404_for_unknown_merchant(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/appointment-flow/{uuid.uuid4()}/info")

    assert response.status_code == 404


async def test_book_appointment_happy_path(client: AsyncClient, db_session: AsyncSession) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _enable_appointment_booking(client, tokens)

    response = await client.post(
        f"/api/v1/appointment-flow/{tenant.merchant_id}/book",
        json={
            "customer_whatsapp_number": "+919876543210",
            "customer_display_name": "Asha",
            "name": "Asha Rao",
            "email": "asha@example.com",
            "appointment_date": "2026-09-01",
            "appointment_time": "18:00:00",
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


async def test_book_appointment_404_when_toggle_off(
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
            "appointment_date": "2026-09-01",
            "appointment_time": "18:00:00",
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
            "appointment_date": "2026-09-01",
            "appointment_time": "18:00:00",
        },
    )

    assert response.status_code == 404


async def test_book_appointment_past_date_returns_400(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _enable_appointment_booking(client, tokens)

    response = await client.post(
        f"/api/v1/appointment-flow/{tenant.merchant_id}/book",
        json={
            "customer_whatsapp_number": "+919876543210",
            "name": "Asha Rao",
            "email": "asha@example.com",
            "appointment_date": "2020-01-01",
            "appointment_time": "18:00:00",
        },
    )

    assert response.status_code == 400


async def test_book_appointment_invalid_email_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _enable_appointment_booking(client, tokens)

    response = await client.post(
        f"/api/v1/appointment-flow/{tenant.merchant_id}/book",
        json={
            "customer_whatsapp_number": "+919876543210",
            "name": "Asha Rao",
            "email": "not-an-email",
            "appointment_date": "2026-09-01",
            "appointment_time": "18:00:00",
        },
    )

    assert response.status_code == 422


async def test_appointment_flow_isolated_between_merchants(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    tenant_a = await _tenant_for(client, tokens_a)
    await _enable_appointment_booking(client, tokens_a)

    tokens_b = await _register(client, owner_contact="owner-b@example.com")

    response = await client.post(
        f"/api/v1/appointment-flow/{tenant_a.merchant_id}/book",
        json={
            "customer_whatsapp_number": "+919876543210",
            "name": "Asha Rao",
            "email": "asha@example.com",
            "appointment_date": "2026-09-01",
            "appointment_time": "18:00:00",
        },
    )
    assert response.status_code == 201, response.text

    # Merchant B's dashboard never sees merchant A's appointment.
    response_b = await client.get("/api/v1/appointments", headers=_auth_headers(tokens_b))
    assert response_b.json() == []
