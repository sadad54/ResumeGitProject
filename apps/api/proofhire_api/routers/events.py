"""SSE run-progress stream (PRD §23 "Streaming": SSE before WebSockets, ADR-0008).

Reads the run's Redis stream, which the worker appends to
(proofhire_worker/events.py), and forwards each entry as an SSE event with
its stream id, so a client never misses an event published before it
connected: it reads from `after` (the position its trigger request returned
as `events_after`) or, reconnecting, from `Last-Event-ID`.
"""

import json
import re
import uuid
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from proofhire_contracts.run_events import run_stream_key
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from proofhire_api.config import get_settings
from proofhire_api.db import get_db
from proofhire_api.dependencies import get_current_user
from proofhire_api.models.generation_run import GenerationRun
from proofhire_api.models.job import Job
from proofhire_api.models.sync_run import SyncRun
from proofhire_api.models.user import User
from proofhire_api.redis_client import get_redis

router = APIRouter(prefix="/api/v1/events", tags=["events"])

_TERMINAL_EVENTS = frozenset(
    {"generation.completed", "generation.failed", "github.sync.completed", "github.sync.failed"}
)
_STREAM_ID = re.compile(r"^\d+-\d+$")


async def stream_position(run_id: uuid.UUID | str) -> str:
    """The id of the newest event already in the run's stream, or 0-0 when
    there is none. Trigger endpoints return it before enqueueing, so a client
    reading after it sees every event of the work it just started and none
    from earlier runs on the same key (generation reuses the job id)."""
    latest = await get_redis().xrevrange(run_stream_key(str(run_id)), count=1)
    return latest[0][0] if latest else "0-0"


async def _event_stream(run_id: str, cursor: str | None):
    client = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    key = run_stream_key(run_id)
    try:
        if cursor is None:
            # "Only what's new", resolved to a concrete id now: re-reading
            # with "$" on every iteration would drop anything that arrived
            # between two blocking reads.
            latest = await client.xrevrange(key, count=1)
            cursor = latest[0][0] if latest else "0-0"
        while True:
            entries = await client.xread({key: cursor}, block=30_000, count=100)
            if not entries:
                yield {"event": "ping", "data": "{}"}
                continue
            for _key, messages in entries:
                for entry_id, fields in messages:
                    cursor = entry_id
                    payload = json.loads(fields["payload"])
                    yield {"id": entry_id, "event": payload["event"],
                           "data": json.dumps(payload["data"])}
                    # A GitHub sync covers several repositories (one
                    # github.repo.completed each) and ends with exactly one
                    # github.sync.completed / .failed.
                    if payload["event"] in _TERMINAL_EVENTS:
                        return
    finally:
        await client.aclose()


@router.get("/runs/{run_id}")
async def stream_run_events(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    # Annotated, so a direct call (tests) gets real None defaults.
    after: Annotated[
        str | None,
        Query(description="Replay events after this stream id (a trigger's events_after)"),
    ] = None,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
):
    cursor = last_event_id or after
    if cursor is not None and not _STREAM_ID.match(cursor):
        raise HTTPException(422, "after / Last-Event-ID must be a stream id like 1727500000000-0")
    for model in (Job, SyncRun, GenerationRun):
        run = await db.get(model, run_id)
        if run is not None and run.user_id == current_user.id:
            return EventSourceResponse(_event_stream(str(run_id), cursor))
    raise HTTPException(404, "Run not found")
