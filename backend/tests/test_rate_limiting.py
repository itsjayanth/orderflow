from httpx import AsyncClient

from tests.test_identity import _register


async def test_login_rate_limit_triggers_429(client: AsyncClient) -> None:
    """/api/v1/auth/login is limited to 10/minute per IP (see the
    @limiter.limit(...) comment in identity/api/router.py). Hammer it past
    that in a tight loop and confirm the limiter actually kicks in, rather
    than just trusting the decorator is wired up correctly."""
    await _register(client)

    statuses = []
    for _ in range(15):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email_or_phone": "owner@example.com", "password": "wrong-password"},
        )
        statuses.append(response.status_code)

    # Every attempt before the limiter kicks in is a normal 401 (wrong
    # password); once it kicks in, everything after is 429.
    assert 429 in statuses, statuses
    first_429 = statuses.index(429)
    assert all(s == 401 for s in statuses[:first_429])
    assert all(s == 429 for s in statuses[first_429:])
    # The limit is 10/minute, so the 11th request (index 10) is the
    # earliest one that can be rejected.
    assert first_429 >= 10

    limited_response = await client.post(
        "/api/v1/auth/login",
        json={"email_or_phone": "owner@example.com", "password": "wrong-password"},
    )
    assert limited_response.status_code == 429
    # Matches this app's normal HTTPException error shape ({"detail": ...}),
    # not slowapi's default {"error": ...} body -- see app.py's
    # rate_limit_exceeded_handler.
    assert "detail" in limited_response.json()
    assert "Rate limit exceeded" in limited_response.json()["detail"]


async def test_register_rate_limit_triggers_429(client: AsyncClient) -> None:
    """/api/v1/auth/register is limited to 10/minute per IP, independently
    of /login's limit (slowapi keys by endpoint as well as IP)."""
    statuses = []
    for i in range(15):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "business_name": "Test Business",
                "owner_name": "Jane Owner",
                "owner_contact": f"owner{i}@example.com",
                "password": "correct-horse-battery-staple",
            },
        )
        statuses.append(response.status_code)

    assert 429 in statuses, statuses
    assert all(s in (201, 429) for s in statuses)
