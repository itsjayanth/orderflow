from shared.config import Settings


def test_postgres_scheme_is_rewritten_to_asyncpg() -> None:
    settings = Settings(database_url="postgres://user:pass@host/db")

    assert settings.database_url == "postgresql+asyncpg://user:pass@host/db"


def test_postgresql_scheme_is_rewritten_to_asyncpg() -> None:
    settings = Settings(database_url="postgresql://user:pass@host/db")

    assert settings.database_url == "postgresql+asyncpg://user:pass@host/db"


def test_asyncpg_scheme_is_left_unchanged() -> None:
    url = "postgresql+asyncpg://user:pass@host/db"

    settings = Settings(database_url=url)

    assert settings.database_url == url


def test_is_production_reflects_env() -> None:
    assert Settings(env="development").is_production is False
    assert Settings(env="production").is_production is True
