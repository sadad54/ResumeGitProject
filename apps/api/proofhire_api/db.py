"""Async SQLAlchemy engine/session setup.

The engine is cached **per event loop** rather than in a single module global.
asyncpg connections are bound to the loop that opened them, so one shared pool
is only safe while the process has exactly one loop for its entire life. That
holds for the API under uvicorn, but not for: TestClient (which runs its own
portal loop, separate from pytest-asyncio's), scripts calling `asyncio.run`
more than once, or any mix of the two in one process. The failure mode is a
confusing `Event loop is closed` / `attached to a different loop` error raised
from a perfectly healthy database.

Same constraint, same remedy as `proofhire_api.redis_client`, and the same root
cause as the worker's NullPool engine in `proofhire_worker.db` (which solves it
differently because Dramatiq creates a fresh loop per task, making per-loop
pooling pointless there).
"""

import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from proofhire_api.config import get_settings

settings = get_settings()

_engines: dict[int, object] = {}
_sessionmakers: dict[int, async_sessionmaker[AsyncSession]] = {}


def get_engine():
    loop_id = id(asyncio.get_running_loop())
    engine = _engines.get(loop_id)
    if engine is None:
        engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
        _engines[loop_id] = engine
    return engine


def _sessionmaker_for_current_loop() -> async_sessionmaker[AsyncSession]:
    loop_id = id(asyncio.get_running_loop())
    maker = _sessionmakers.get(loop_id)
    if maker is None:
        maker = async_sessionmaker(get_engine(), expire_on_commit=False)
        _sessionmakers[loop_id] = maker
    return maker


class _SessionFactory:
    """Callable stand-in for an `async_sessionmaker`.

    Kept callable so every existing `async with async_session_factory() as
    session:` call site keeps working unchanged, while resolution of the
    underlying engine happens at call time, on the loop that will actually use
    the connection.
    """

    def __call__(self) -> AsyncSession:
        return _sessionmaker_for_current_loop()()


async_session_factory = _SessionFactory()


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
