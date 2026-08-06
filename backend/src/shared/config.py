from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+asyncpg://orderflow:orderflow@localhost:5432/orderflow"

    jwt_secret: str = "change-me"
    jwt_access_token_ttl_minutes: int = 15
    jwt_refresh_token_ttl_days: int = 30

    secrets_encryption_key: str = ""

    # Razorpay and WhatsApp credentials are per-merchant (Settings page),
    # not global -- see payments/domain/models.py's
    # MerchantPaymentCredentials and onboarding/domain/models.py's
    # WhatsAppBusinessAccount.
    whatsapp_graph_api_base_url: str = "https://graph.facebook.com/v20.0"

    abandoned_order_timeout_minutes: int = 30

    cors_allow_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
