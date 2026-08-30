from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+asyncpg://orderflow:orderflow@localhost:5432/orderflow"

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg_driver(cls, value: str) -> str:
        """Render's Postgres connection string (like most hosts') comes as
        `postgres://` or `postgresql://` -- the app needs the `+asyncpg`
        driver suffix for SQLAlchemy's async engine. Rewritten here once
        rather than requiring every deploy target to hand-edit the URL."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix) and "+asyncpg" not in value:
                return "postgresql+asyncpg://" + value[len(prefix) :]
        return value

    @property
    def is_production(self) -> bool:
        return self.env != "development"

    jwt_secret: str = "change-me"
    jwt_access_token_ttl_minutes: int = 15
    jwt_refresh_token_ttl_days: int = 30

    secrets_encryption_key: str = ""

    # Razorpay and WhatsApp credentials are per-merchant (Settings page),
    # not global -- see payments/domain/models.py's
    # MerchantPaymentCredentials and onboarding/domain/models.py's
    # WhatsAppBusinessAccount.
    whatsapp_graph_api_base_url: str = "https://graph.facebook.com/v20.0"
    # Shared across all merchants -- Meta's webhook verification handshake
    # is per-app, not per-tenant (the callback URL itself is shared infra).
    whatsapp_webhook_verify_token: str = "change-me"

    # Meta Embedded Signup (onboarding/domain/embedded_signup.py) -- one
    # Meta App backs every merchant's "Connect WhatsApp" button, the same
    # way whatsapp_webhook_verify_token above is app-wide, not per-merchant.
    # Unset by default: the connect button hides itself (frontend checks
    # VITE_META_APP_ID/VITE_META_ES_CONFIG_ID) and the backend endpoint
    # fails fast with a clear error rather than a confusing Meta 4xx.
    #
    # Decided 2026-08-30: reuses fastflow/ORDZO's existing "OrdzoLive" Meta
    # App (App ID 1012236041846794, App Review-approved for
    # whatsapp_business_management/whatsapp_business_messaging) rather than
    # registering a separate app -- same company, same App Review approval
    # covers both products. A dedicated Facebook Login for Business
    # configuration ("Orderflow Embedded Signup", config_id 2032001420768003)
    # was created scoped to orderflow's own domain, and
    # orderflow-sandbox.vercel.app was added to that app's Allowed Domains
    # for the JavaScript SDK. Because the app is shared, WABA webhook
    # subscription MUST use an override_callback_uri pointing at
    # orderflow's own backend -- see embedded_signup.py's
    # _subscribe_app_to_waba docstring; relying on the app's default
    # Callback URL would route events to fastflow's backend instead.
    meta_app_id: str | None = None
    meta_app_secret: str | None = None
    # The Facebook Login for Business "WhatsApp Embedded Signup" config_id
    # from the Meta App Dashboard -- the frontend needs the same value as
    # VITE_META_ES_CONFIG_ID for FB.login(), but nothing here reads it
    # server-side; kept for symmetry/documentation of what must be set.
    meta_es_config_id: str | None = None
    # Deliberately independent of whatsapp_graph_api_base_url's baked-in
    # v20.0 (existing send/Flow code, untouched here) -- new Embedded
    # Signup calls (oauth/access_token, debug_token, subscribed_apps,
    # register) use this instead so they aren't stuck on a stale pin.
    meta_graph_api_version: str = "v22.0"

    # Where the customer-facing ordering webview lives, for links the bot
    # sends in-chat (see conversation/domain/handler.py).
    frontend_base_url: str = "http://localhost:5173"

    abandoned_order_timeout_minutes: int = 30

    cors_allow_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
