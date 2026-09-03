import datetime
import itertools
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from appointments.adapters.repository import AppointmentNotFoundError, AppointmentRepository
from appointments.domain.state_machine import IllegalTransitionError
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from shared.tenant import TenantContext

# Overlap prevention (AppointmentRepository._assert_no_overlap) means two
# _seed_appointment calls for the same tenant/date can no longer silently
# share the same default time -- generate a fresh one per call so tests
# that seed several appointments and don't care about the exact time (most
# of them) don't collide with each other.
_next_seed_hour = itertools.count(9)


async def _make_tenant(
    db_session: AsyncSession, business_name: str = "Test Business"
) -> TenantContext:
    merchant = await MerchantRepository(db_session).create(
        business_name=business_name, owner_contact=f"{uuid.uuid4()}@example.com"
    )
    return TenantContext(merchant_id=merchant.merchant_id)


async def _register(client: AsyncClient, owner_contact: str = "owner@example.com") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Test Business",
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


async def _seed_appointment(
    db_session: AsyncSession,
    tenant: TenantContext,
    *,
    status: str = "requested",
    customer_whatsapp_number: str = "+919876543210",
    customer_display_name: str | None = None,
    appointment_date: datetime.date | None = None,
    start_time: datetime.time | None = None,
    notes: str | None = None,
):
    customer = await CustomerRepository(db_session).find_or_create(
        tenant, customer_whatsapp_number, display_name=customer_display_name
    )
    if start_time is None:
        start_time = datetime.time(next(_next_seed_hour) % 24, 0)
    end_time = (
        datetime.datetime.combine(datetime.date.min, start_time) + datetime.timedelta(minutes=30)
    ).time()
    appointment = await AppointmentRepository(db_session).create(
        tenant,
        customer_id=customer.customer_id,
        name="Asha Rao",
        email="asha@example.com",
        appointment_date=appointment_date or datetime.date(2026, 9, 1),
        start_time=start_time,
        end_time=end_time,
        notes=notes,
    )
    if status != "requested":
        from appointments.domain.state_machine import transition_status

        transition_status(appointment, status)
    await db_session.commit()
    return appointment


# --- AppointmentRepository.create + numbering -------------------------------


async def test_appointment_numbers_increment_sequentially_per_merchant(
    db_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(db_session)
    first = await _seed_appointment(db_session, tenant)
    second = await _seed_appointment(db_session, tenant)
    third = await _seed_appointment(db_session, tenant)

    assert [first.appointment_number, second.appointment_number, third.appointment_number] == [
        1,
        2,
        3,
    ]


async def test_appointment_numbers_isolated_per_merchant(db_session: AsyncSession) -> None:
    tenant_a = await _make_tenant(db_session, business_name="Business A")
    tenant_b = await _make_tenant(db_session, business_name="Business B")

    appointment_a1 = await _seed_appointment(db_session, tenant_a)
    appointment_b1 = await _seed_appointment(db_session, tenant_b)
    appointment_a2 = await _seed_appointment(db_session, tenant_a)

    assert appointment_a1.appointment_number == 1
    assert appointment_b1.appointment_number == 1
    assert appointment_a2.appointment_number == 2


async def test_created_appointment_status_defaults_to_requested(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    appointment = await _seed_appointment(db_session, tenant)

    assert appointment.status == "requested"


# --- repository-level "defense in depth" transition test --------------------


async def test_repository_rejects_illegal_transition(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    appointment = await _seed_appointment(db_session, tenant, status="requested")
    repo = AppointmentRepository(db_session)

    with pytest.raises(IllegalTransitionError):
        await repo.transition_status(
            tenant, appointment.appointment_id, "completed", changed_by="staff-1"
        )


async def test_repository_transition_nonexistent_appointment_raises(
    db_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(db_session)
    repo = AppointmentRepository(db_session)

    with pytest.raises(AppointmentNotFoundError):
        await repo.transition_status(tenant, uuid.uuid4(), "confirmed", changed_by="staff-1")


# --- API endpoints -----------------------------------------------------


async def test_list_appointments_empty(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.get("/api/v1/appointments", headers=_auth_headers(tokens))

    assert response.status_code == 200
    assert response.json() == []


async def test_list_appointments_returns_seeded_appointment(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    appointment = await _seed_appointment(db_session, tenant, customer_display_name="Asha Rao")

    response = await client.get("/api/v1/appointments", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["appointment_id"] == str(appointment.appointment_id)
    assert body[0]["appointment_number"] == appointment.appointment_number
    assert body[0]["status"] == "requested"
    assert body[0]["customer_name"] == "Asha Rao"
    assert body[0]["customer_whatsapp_number"] == "919876543210"
    assert body[0]["customer_number"] == 1
    assert body[0]["name"] == "Asha Rao"
    assert body[0]["email"] == "asha@example.com"


async def test_list_appointments_ordered_soonest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    later = await _seed_appointment(
        db_session, tenant, appointment_date=datetime.date(2026, 10, 1)
    )
    sooner = await _seed_appointment(db_session, tenant, appointment_date=datetime.date(2026, 9, 1))

    response = await client.get("/api/v1/appointments", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert [row["appointment_id"] for row in body] == [
        str(sooner.appointment_id),
        str(later.appointment_id),
    ]


async def test_list_appointments_filtered_by_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _seed_appointment(db_session, tenant, status="requested")
    await _seed_appointment(db_session, tenant, status="confirmed")

    response = await client.get(
        "/api/v1/appointments", params={"status": "confirmed"}, headers=_auth_headers(tokens)
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "confirmed"


async def test_list_appointments_filtered_by_date_range(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _seed_appointment(db_session, tenant, appointment_date=datetime.date(2026, 1, 1))
    in_range = await _seed_appointment(
        db_session, tenant, appointment_date=datetime.date(2026, 1, 15)
    )
    await _seed_appointment(db_session, tenant, appointment_date=datetime.date(2026, 2, 1))

    response = await client.get(
        "/api/v1/appointments",
        params={"from_date": "2026-01-10", "to_date": "2026-01-20"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["appointment_id"] == str(in_range.appointment_id)


async def test_list_appointments_filtered_by_customer_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    matching = await _seed_appointment(
        db_session, tenant, customer_whatsapp_number="+919876543210"
    )
    await _seed_appointment(db_session, tenant, customer_whatsapp_number="+919876543211")

    response = await client.get(
        "/api/v1/appointments",
        params={"customer_id": str(matching.customer_id)},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["appointment_id"] == str(matching.appointment_id)


async def test_get_appointment_detail(client: AsyncClient, db_session: AsyncSession) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    appointment = await _seed_appointment(db_session, tenant, customer_display_name="Asha Rao")

    response = await client.get(
        f"/api/v1/appointments/{appointment.appointment_id}", headers=_auth_headers(tokens)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["appointment_id"] == str(appointment.appointment_id)
    assert body["customer_name"] == "Asha Rao"


async def test_get_appointment_not_found(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.get(
        f"/api/v1/appointments/{uuid.uuid4()}", headers=_auth_headers(tokens)
    )

    assert response.status_code == 404


async def test_update_appointment_status_happy_path(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    appointment = await _seed_appointment(db_session, tenant, status="requested")

    response = await client.patch(
        f"/api/v1/appointments/{appointment.appointment_id}/status",
        json={"to_status": "confirmed"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["confirmed_at"] is not None


async def test_appointment_history_resolves_staff_name_for_status_changes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The history timeline shows the acting staff member's actual name,
    not their raw staff_user_id -- resolved fresh on read (not stored on
    the event row), same as any other current-state lookup in this app."""
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    appointment = await _seed_appointment(db_session, tenant, status="requested")

    await client.patch(
        f"/api/v1/appointments/{appointment.appointment_id}/status",
        json={"to_status": "confirmed"},
        headers=_auth_headers(tokens),
    )

    response = await client.get(
        f"/api/v1/appointments/{appointment.appointment_id}", headers=_auth_headers(tokens)
    )

    assert response.status_code == 200
    events = response.json()["status_events"]
    confirmed_event = next(e for e in events if e["event_type"] == "confirmed")
    assert confirmed_event["changed_by_name"] == "Jane Owner"

    requested_event = next(e for e in events if e["event_type"] == "requested")
    # The initial request has no staff actor -- created_via ("browser" by
    # default, see _seed_appointment), not a resolvable name.
    assert requested_event["changed_by_name"] is None


async def test_update_appointment_status_illegal_transition_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    appointment = await _seed_appointment(db_session, tenant, status="requested")

    response = await client.patch(
        f"/api/v1/appointments/{appointment.appointment_id}/status",
        json={"to_status": "completed"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 409


async def test_update_appointment_status_not_found_returns_404(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.patch(
        f"/api/v1/appointments/{uuid.uuid4()}/status",
        json={"to_status": "confirmed"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 404


async def test_update_appointment_status_invalid_value_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    appointment = await _seed_appointment(db_session, tenant, status="requested")

    response = await client.patch(
        f"/api/v1/appointments/{appointment.appointment_id}/status",
        json={"to_status": "not-a-real-status"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 422


async def test_appointments_isolated_between_merchants(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    tenant_a = await _tenant_for(client, tokens_a)
    tokens_b = await _register(client, owner_contact="owner-b@example.com")
    appointment_a = await _seed_appointment(db_session, tenant_a)

    list_response = await client.get("/api/v1/appointments", headers=_auth_headers(tokens_b))
    assert list_response.status_code == 200
    assert list_response.json() == []

    detail_response = await client.get(
        f"/api/v1/appointments/{appointment_a.appointment_id}", headers=_auth_headers(tokens_b)
    )
    assert detail_response.status_code == 404

    update_response = await client.patch(
        f"/api/v1/appointments/{appointment_a.appointment_id}/status",
        json={"to_status": "confirmed"},
        headers=_auth_headers(tokens_b),
    )
    assert update_response.status_code == 404


# --- Dashboard edit: notes -----------------------------------------------


async def test_update_appointment_notes(client: AsyncClient, db_session: AsyncSession) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    appointment = await _seed_appointment(db_session, tenant)

    response = await client.patch(
        f"/api/v1/appointments/{appointment.appointment_id}",
        json={"notes": "Window seat please"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json()["notes"] == "Window seat please"


async def test_update_appointment_notes_not_found(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.patch(
        f"/api/v1/appointments/{uuid.uuid4()}",
        json={"notes": "Window seat please"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 404
