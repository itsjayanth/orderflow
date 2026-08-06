import datetime
from collections.abc import AsyncIterator

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from shared.config import get_settings


class Base(DeclarativeBase):
    # Every Mapped[datetime.datetime] column is timezone-aware by default —
    # models create tz-aware UTC values (datetime.now(datetime.UTC)), and a
    # naive TIMESTAMP column rejects those under asyncpg's strict driver.
    type_annotation_map = {
        datetime.datetime: DateTime(timezone=True),
    }


engine = create_async_engine(get_settings().database_url, echo=False)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
