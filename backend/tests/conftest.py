import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://orderflow:orderflow@localhost:5432/orderflow_test"
)
# Tests assert on WHATSAPP_FLOW-mode behavior by default (only
# test_interaction_mode.py and the BROWSER_LINK-specific handler tests
# override it themselves) -- pinning this here keeps the suite deterministic
# regardless of what a developer's local backend/.env sets INTERACTION_MODE
# to, the same way DATABASE_URL is pinned above rather than trusting .env.
os.environ.setdefault("INTERACTION_MODE", "WHATSAPP_FLOW")

# JWT_SECRET/WHATSAPP_WEBHOOK_VERIFY_TOKEN/META_APP_SECRET have no
# hardcoded default in shared/config.py on purpose (a guessable default
# would defeat auth/webhook-signature verification in production) -- so
# the suite needs its own deterministic, test-only values, the same
# rationale as INTERACTION_MODE above. Individual tests that need a
# specific value (e.g. test_verify_webhook_with_correct_token) still
# monkeypatch + get_settings.cache_clear() over these.
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
os.environ.setdefault("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "test-only-webhook-verify-token")
os.environ.setdefault("META_APP_SECRET", "test-only-meta-app-secret")
# PAYMENTS_DUMMY_GATEWAY_SECRET/PLATFORM_RAZORPAY_WEBHOOK_SECRET default to a
# random value generated at process startup (shared/config.py) when unset,
# same "no guessable committed default" reasoning as the three above --
# pinned here for the same test-determinism reason.
os.environ.setdefault("PAYMENTS_DUMMY_GATEWAY_SECRET", "test-only-payments-dummy-gateway-secret")
os.environ.setdefault(
    "PLATFORM_RAZORPAY_WEBHOOK_SECRET", "test-only-platform-razorpay-webhook-secret"
)

import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Importing `app` (rather than listing individual `<module>.domain.models`
# imports) registers every module's models on Base.metadata transitively,
# since app -> dashboard_api's router -> every domain module's router ->
# that module's models. New modules never need to touch this file.
from app import app
from billing.domain.models import Plan
from billing.domain.seed_data import SEED_PLANS
from shared.db import Base, SessionFactory, engine


def webhook_request_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    """Builds the (content, headers) httpx.post() kwargs for a WhatsApp
    webhook POST, signed with the same META_APP_SECRET this conftest pins
    -- conversation/api/router.py rejects any POST without a valid
    X-Hub-Signature-256 header. Use this instead of `json=payload` for any
    POST to /api/v1/whatsapp/webhook."""
    body = json.dumps(payload).encode("utf-8")
    secret = os.environ["META_APP_SECRET"]
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return {
        "content": body,
        "headers": {
            "content-type": "application/json",
            "x-hub-signature-256": f"sha256={signature}",
        },
    }


@pytest_asyncio.fixture(autouse=True)
async def _reset_db() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Tests recreate schema via Base.metadata.create_all rather than
    # running Alembic migrations, so the billing_plans seed migration's
    # data-seed step never runs here -- reseed the same SEED_PLANS rows
    # directly (registration creates a Subscription against the seeded
    # Growth plan, so most of the suite transitively depends on this
    # existing, not just billing's own tests).
    async with SessionFactory() as session:
        session.add_all(
            Plan(**{**plan, "price_inr": Decimal(str(plan["price_inr"]))})
            for plan in SEED_PLANS
        )
        await session.commit()

    yield


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
