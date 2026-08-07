from httpx import AsyncClient


async def _register(client: AsyncClient, owner_contact: str = "owner@example.com") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Test Kitchen",
            "owner_name": "Jane Owner",
            "owner_contact": owner_contact,
            "password": "correct-horse-battery-staple",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_create_then_list_menu_item(client: AsyncClient) -> None:
    tokens = await _register(client)

    create_response = await client.post(
        "/api/v1/catalog/items",
        json={"category": "Mains", "name": "Butter Chicken", "price": "349.00"},
        headers=_auth_headers(tokens),
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["category"] == "Mains"
    assert created["name"] == "Butter Chicken"
    assert created["price"] == "349.00"
    assert created["is_available"] is True
    assert created["item_number"] == 1

    list_response = await client.get("/api/v1/catalog/items", headers=_auth_headers(tokens))
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["menu_item_id"] == created["menu_item_id"]


async def test_item_numbers_increment_sequentially_per_merchant(client: AsyncClient) -> None:
    tokens = await _register(client)

    numbers = []
    for name in ("Butter Chicken", "Naan", "Dal Makhani"):
        response = await client.post(
            "/api/v1/catalog/items",
            json={"category": "Mains", "name": name, "price": "100.00"},
            headers=_auth_headers(tokens),
        )
        assert response.status_code == 201, response.text
        numbers.append(response.json()["item_number"])

    assert numbers == [1, 2, 3]


async def test_item_numbers_isolated_per_merchant(client: AsyncClient) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    tokens_b = await _register(client, owner_contact="owner-b@example.com")

    response_a = await client.post(
        "/api/v1/catalog/items",
        json={"category": "Mains", "name": "Butter Chicken", "price": "100.00"},
        headers=_auth_headers(tokens_a),
    )
    response_b = await client.post(
        "/api/v1/catalog/items",
        json={"category": "Mains", "name": "Paneer Tikka", "price": "100.00"},
        headers=_auth_headers(tokens_b),
    )

    assert response_a.json()["item_number"] == 1
    assert response_b.json()["item_number"] == 1


async def test_update_menu_item(client: AsyncClient) -> None:
    tokens = await _register(client)

    create_response = await client.post(
        "/api/v1/catalog/items",
        json={"category": "Mains", "name": "Butter Chicken", "price": "349.00"},
        headers=_auth_headers(tokens),
    )
    menu_item_id = create_response.json()["menu_item_id"]

    update_response = await client.patch(
        f"/api/v1/catalog/items/{menu_item_id}",
        json={"is_available": False, "price": "399.00"},
        headers=_auth_headers(tokens),
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["is_available"] is False
    assert updated["price"] == "399.00"
    assert updated["name"] == "Butter Chicken"


async def test_update_nonexistent_menu_item_returns_404(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.patch(
        "/api/v1/catalog/items/00000000-0000-0000-0000-000000000000",
        json={"is_available": False},
        headers=_auth_headers(tokens),
    )
    assert response.status_code == 404


async def test_menu_items_are_tenant_isolated(client: AsyncClient) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    tokens_b = await _register(client, owner_contact="owner-b@example.com")

    create_response = await client.post(
        "/api/v1/catalog/items",
        json={"category": "Mains", "name": "Butter Chicken", "price": "349.00"},
        headers=_auth_headers(tokens_a),
    )
    menu_item_id = create_response.json()["menu_item_id"]

    # Merchant B can't see merchant A's item.
    list_response_b = await client.get("/api/v1/catalog/items", headers=_auth_headers(tokens_b))
    assert list_response_b.json() == []

    # Merchant B can't update merchant A's item either.
    update_response_b = await client.patch(
        f"/api/v1/catalog/items/{menu_item_id}",
        json={"is_available": False},
        headers=_auth_headers(tokens_b),
    )
    assert update_response_b.status_code == 404

    # Merchant A's item is untouched and still visible to merchant A.
    list_response_a = await client.get("/api/v1/catalog/items", headers=_auth_headers(tokens_a))
    items_a = list_response_a.json()
    assert len(items_a) == 1
    assert items_a[0]["is_available"] is True


async def test_create_menu_item_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/catalog/items",
        json={"category": "Mains", "name": "Butter Chicken", "price": "349.00"},
    )
    assert response.status_code == 401
