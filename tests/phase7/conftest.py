"""Real SQL tests on an ephemeral SQLite DB; production migration tests use Postgres."""

import proofhire_api.models  # noqa: F401
import pytest_asyncio
from proofhire_api.db import Base
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()
