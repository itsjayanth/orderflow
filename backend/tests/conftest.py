import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://orderflow:orderflow@localhost:5432/orderflow_test"
)

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Importing `app` (rather than listing individual `<module>.domain.models`
# imports) registers every module's models on Base.metadata transitively,
# since app -> dashboard_api's router -> every domain module's router ->
# that module's models. New modules never need to touch this file.
from app import app
from shared.db import Base, SessionFactory, engine


@pytest_asyncio.fixture(autouse=True)
async def _reset_db() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
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
