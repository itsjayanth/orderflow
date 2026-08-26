import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from identity.adapters.repository import MerchantRepository
from onboarding.domain import embedded_signup as embedded_signup_domain
from onboarding.domain.embedded_signup import (
    EmbeddedSignupError,
    complete_embedded_signup,
    embedded_signup_configured,
)
from onboarding.domain.onboarding_service import get_checklist
from shared.config import get_settings
from shared.encryption import decrypt
from shared.tenant import TenantContext


async def _seed_merchant_tenant(db_session: AsyncSession, business_name: str) -> TenantContext:
    merchant = await MerchantRepository(db_session).create(
        business_name=business_name, owner_contact=f"{business_name}@example.com"
    )
    return TenantContext(merchant_id=merchant.merchant_id)


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._json_body = json_body if json_body is not None else {}
        self.text = text or str(self._json_body)

    def json(self) -> dict:
        return self._json_body


class _FakeSignupClient:
    """Records every call and answers from a per-URL-suffix table -- lets a
    test assert complete_embedded_signup hits Meta's token exchange, phone
    lookup, register, and subscribe_apps endpoints in order, without a real
    network call. Mirrors _FakeAssetUploadClient in test_flows_setup.py."""

    def __init__(self, responses: dict[str, _FakeResponse]) -> None:
        self.calls: list[dict] = []
        self._responses = responses

    async def __aenter__(self) -> "_FakeSignupClient":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    def _respond(self, method: str, url: str, **kwargs: object) -> _FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        for suffix, response in self._responses.items():
            if url.endswith(suffix):
                return response
        raise AssertionError(f"unexpected call to {url}")

    async def get(self, url: str, **kwargs: object) -> _FakeResponse:
        return self._respond("get", url, **kwargs)

    async def post(self, url: str, **kwargs: object) -> _FakeResponse:
        return self._respond("post", url, **kwargs)


def _configure_meta_app(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("META_APP_ID", "123456")
    monkeypatch.setenv("META_APP_SECRET", "app-secret")
    monkeypatch.setenv("META_CONFIGURATION_ID", "cfg-1")
    get_settings.cache_clear()


def test_embedded_signup_configured_reflects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.delenv("META_APP_ID", raising=False)
    monkeypatch.delenv("META_APP_SECRET", raising=False)
    monkeypatch.delenv("META_CONFIGURATION_ID", raising=False)
    get_settings.cache_clear()
    assert embedded_signup_configured() is False

    _configure_meta_app(monkeypatch)
    assert embedded_signup_configured() is True
    get_settings.cache_clear()


async def test_complete_embedded_signup_fails_without_app_credentials(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    get_settings.cache_clear()
    monkeypatch.delenv("META_APP_ID", raising=False)
    monkeypatch.delenv("META_APP_SECRET", raising=False)
    get_settings.cache_clear()
    tenant = await _seed_merchant_tenant(db_session, "No App Creds")

    with pytest.raises(EmbeddedSignupError) as exc_info:
        await complete_embedded_signup(
            db_session, tenant, code="abc", waba_id="waba-1", phone_number_id="phone-1"
        )

    assert exc_info.value.step == "precondition"
    get_settings.cache_clear()


async def test_complete_embedded_signup_persists_credentials_and_advances_onboarding(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_meta_app(monkeypatch)
    tenant = await _seed_merchant_tenant(db_session, "Fresh Signup")

    fake_client = _FakeSignupClient(
        {
            "/oauth/access_token": _FakeResponse(
                200, {"access_token": "long-lived-token", "expires_in": 5184000}
            ),
            "/phone-1": _FakeResponse(200, {"display_phone_number": "+91 90000 00000"}),
            "/phone-1/register": _FakeResponse(200, {"success": True}),
            "/waba-1/subscribed_apps": _FakeResponse(200, {"success": True}),
        }
    )
    monkeypatch.setattr(
        embedded_signup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client
    )

    account = await complete_embedded_signup(
        db_session, tenant, code="auth-code", waba_id="waba-1", phone_number_id="phone-1"
    )

    assert account.phone_number_id == "phone-1"
    assert account.meta_waba_id == "waba-1"
    assert account.display_phone_number == "+91 90000 00000"
    assert account.connection_method == "embedded_signup"
    assert account.connection_status == "connected"
    assert account.webhook_subscribed is True
    assert decrypt(account.access_token_encrypted) == "long-lived-token"
    assert account.two_step_pin_encrypted is not None
    assert account.token_expiry_at is not None

    checklist = await get_checklist(db_session, tenant)
    assert checklist.whatsapp_connected is True

    register_call = next(c for c in fake_client.calls if c["url"].endswith("/phone-1/register"))
    assert register_call["json"]["messaging_product"] == "whatsapp"
    assert len(register_call["json"]["pin"]) == 6


async def test_complete_embedded_signup_raises_on_token_exchange_failure(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_meta_app(monkeypatch)
    tenant = await _seed_merchant_tenant(db_session, "Bad Code")

    fake_client = _FakeSignupClient(
        {"/oauth/access_token": _FakeResponse(400, {"error": "invalid code"})}
    )
    monkeypatch.setattr(
        embedded_signup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client
    )

    with pytest.raises(EmbeddedSignupError) as exc_info:
        await complete_embedded_signup(
            db_session, tenant, code="bad-code", waba_id="waba-1", phone_number_id="phone-1"
        )

    assert exc_info.value.step == "exchange_code"


async def test_complete_embedded_signup_raises_on_register_failure(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_meta_app(monkeypatch)
    tenant = await _seed_merchant_tenant(db_session, "Register Fails")

    fake_client = _FakeSignupClient(
        {
            "/oauth/access_token": _FakeResponse(200, {"access_token": "token"}),
            "/phone-1": _FakeResponse(200, {"display_phone_number": "+91 90000 00000"}),
            "/phone-1/register": _FakeResponse(400, {"error": "already registered"}),
        }
    )
    monkeypatch.setattr(
        embedded_signup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client
    )

    with pytest.raises(EmbeddedSignupError) as exc_info:
        await complete_embedded_signup(
            db_session, tenant, code="auth-code", waba_id="waba-1", phone_number_id="phone-1"
        )

    assert exc_info.value.step == "register_phone_number"
