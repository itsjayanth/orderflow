import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from faq.adapters.repository import FAQItemRepository
from identity.adapters.repository import MerchantRepository
from shared.tenant import TenantContext


async def _make_tenant(
    db_session: AsyncSession, business_name: str = "Test Business"
) -> TenantContext:
    """Repository-level tests need a real Merchant row since merchant_id is a FK."""
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


# --- repository: match() scoring ---


async def test_match_exact_keyword_hit(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    repo = FAQItemRepository(db_session)
    await repo.create(
        tenant,
        question_text="Where are you located?",
        answer_text="We're at 12 MG Road, Bengaluru.",
        keywords=["location", "address", "where"],
    )
    await db_session.commit()

    matches = await repo.match(tenant, "hey what's your location")

    assert len(matches) == 1
    assert matches[0].question_text == "Where are you located?"


async def test_match_returns_nothing_for_unrelated_text(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    repo = FAQItemRepository(db_session)
    await repo.create(
        tenant,
        question_text="Where are you located?",
        answer_text="We're at 12 MG Road, Bengaluru.",
        keywords=["location", "address", "where"],
    )
    await db_session.commit()

    matches = await repo.match(tenant, "do you have gluten free options")

    assert matches == []


async def test_match_ignores_inactive_items(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    repo = FAQItemRepository(db_session)
    item = await repo.create(
        tenant,
        question_text="Where are you located?",
        answer_text="We're at 12 MG Road, Bengaluru.",
        keywords=["location", "address", "where"],
    )
    await repo.update(tenant, item.faq_item_id, is_active=False)
    await db_session.commit()

    matches = await repo.match(tenant, "what's your location")

    assert matches == []


async def test_match_ties_are_broken_by_creation_order(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    repo = FAQItemRepository(db_session)
    first = await repo.create(
        tenant,
        question_text="What are your timings?",
        answer_text="We're open 11am-11pm.",
        keywords=["timings", "hours"],
    )
    second = await repo.create(
        tenant,
        question_text="When do you open?",
        answer_text="We're open 11am-11pm.",
        keywords=["timings", "hours"],
    )
    await db_session.commit()

    matches = await repo.match(tenant, "what are your timings and hours")

    assert [m.faq_item_id for m in matches] == [first.faq_item_id, second.faq_item_id]


async def test_match_empty_text_returns_nothing(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    repo = FAQItemRepository(db_session)
    await repo.create(
        tenant,
        question_text="Where are you located?",
        answer_text="We're at 12 MG Road, Bengaluru.",
        keywords=["location", "address", "where"],
    )
    await db_session.commit()

    matches = await repo.match(tenant, "   ")

    assert matches == []


# --- repository: tenant isolation ---


async def test_match_is_tenant_isolated(db_session: AsyncSession) -> None:
    tenant_a = await _make_tenant(db_session, business_name="Business A")
    tenant_b = await _make_tenant(db_session, business_name="Business B")
    repo = FAQItemRepository(db_session)
    await repo.create(
        tenant_a,
        question_text="Where are you located?",
        answer_text="We're at 12 MG Road, Bengaluru.",
        keywords=["location", "address", "where"],
    )
    await db_session.commit()

    matches_for_b = await repo.match(tenant_b, "what's your location")

    assert matches_for_b == []


async def test_list_is_tenant_isolated(db_session: AsyncSession) -> None:
    tenant_a = await _make_tenant(db_session, business_name="Business A")
    tenant_b = await _make_tenant(db_session, business_name="Business B")
    repo = FAQItemRepository(db_session)
    await repo.create(
        tenant_a,
        question_text="Where are you located?",
        answer_text="We're at 12 MG Road, Bengaluru.",
        keywords=["location"],
    )
    await db_session.commit()

    assert await repo.list(tenant_b) == []
    assert len(await repo.list(tenant_a)) == 1


# --- API CRUD round trip ---


async def test_create_then_list_faq_item(client: AsyncClient) -> None:
    tokens = await _register(client)

    create_response = await client.post(
        "/api/v1/faq/items",
        json={
            "question_text": "Where are you located?",
            "answer_text": "We're at 12 MG Road, Bengaluru.",
            "keywords": ["location", "address", "where"],
        },
        headers=_auth_headers(tokens),
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["question_text"] == "Where are you located?"
    assert created["answer_text"] == "We're at 12 MG Road, Bengaluru."
    assert created["keywords"] == ["location", "address", "where"]
    assert created["is_active"] is True

    list_response = await client.get("/api/v1/faq/items", headers=_auth_headers(tokens))
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["faq_item_id"] == created["faq_item_id"]


async def test_update_faq_item(client: AsyncClient) -> None:
    tokens = await _register(client)

    create_response = await client.post(
        "/api/v1/faq/items",
        json={
            "question_text": "Where are you located?",
            "answer_text": "We're at 12 MG Road, Bengaluru.",
            "keywords": ["location"],
        },
        headers=_auth_headers(tokens),
    )
    faq_item_id = create_response.json()["faq_item_id"]

    update_response = await client.patch(
        f"/api/v1/faq/items/{faq_item_id}",
        json={"answer_text": "We're at 45 Residency Road, Bengaluru."},
        headers=_auth_headers(tokens),
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["answer_text"] == "We're at 45 Residency Road, Bengaluru."
    assert updated["question_text"] == "Where are you located?"


async def test_soft_delete_faq_item_via_is_active(client: AsyncClient) -> None:
    tokens = await _register(client)

    create_response = await client.post(
        "/api/v1/faq/items",
        json={
            "question_text": "Where are you located?",
            "answer_text": "We're at 12 MG Road, Bengaluru.",
            "keywords": ["location"],
        },
        headers=_auth_headers(tokens),
    )
    faq_item_id = create_response.json()["faq_item_id"]

    delete_response = await client.patch(
        f"/api/v1/faq/items/{faq_item_id}",
        json={"is_active": False},
        headers=_auth_headers(tokens),
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["is_active"] is False

    # Soft-deleted items still show up in the dashboard listing...
    list_response = await client.get("/api/v1/faq/items", headers=_auth_headers(tokens))
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["is_active"] is False


async def test_update_nonexistent_faq_item_returns_404(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.patch(
        "/api/v1/faq/items/00000000-0000-0000-0000-000000000000",
        json={"is_active": False},
        headers=_auth_headers(tokens),
    )
    assert response.status_code == 404


async def test_faq_items_are_tenant_isolated(client: AsyncClient) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    tokens_b = await _register(client, owner_contact="owner-b@example.com")

    create_response = await client.post(
        "/api/v1/faq/items",
        json={
            "question_text": "Where are you located?",
            "answer_text": "We're at 12 MG Road, Bengaluru.",
            "keywords": ["location"],
        },
        headers=_auth_headers(tokens_a),
    )
    faq_item_id = create_response.json()["faq_item_id"]

    list_response_b = await client.get("/api/v1/faq/items", headers=_auth_headers(tokens_b))
    assert list_response_b.json() == []

    update_response_b = await client.patch(
        f"/api/v1/faq/items/{faq_item_id}",
        json={"is_active": False},
        headers=_auth_headers(tokens_b),
    )
    assert update_response_b.status_code == 404


async def test_create_faq_item_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/faq/items",
        json={
            "question_text": "Where are you located?",
            "answer_text": "We're at 12 MG Road, Bengaluru.",
            "keywords": ["location"],
        },
    )
    assert response.status_code == 401
