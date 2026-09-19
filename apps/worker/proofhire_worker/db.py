"""Async DB session factory for worker tasks.

Each Dramatiq actor entrypoint drives its async pipeline stage via its own
asyncio.run() call (see e.g. ingestion/sync.py's sync_repositories), which
creates a brand-new event loop per task. asyncpg connections are bound to the
event loop they were opened on, so a connection pool (proofhire_api.db's engine,
built for the API's single long-lived uvicorn loop) crashes once a connection
opened under one task's loop is handed to a later task's new loop:
"got Future ... attached to a different loop". NullPool avoids this: every
session opens its own physical connection and closes it within its own task's
event loop, so none is ever reused across a loop boundary.
"""

from proofhire_api.config import get_settings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

engine = create_async_engine(get_settings().database_url, echo=False, poolclass=NullPool)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
