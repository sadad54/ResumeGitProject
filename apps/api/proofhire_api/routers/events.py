"""SSE run-progress stream (PRD §23 "Streaming": SSE before WebSockets, ADR-0008).

Subscribes to the same Redis pub/sub channel the worker publishes to
(proofhire_worker/events.py) and forwards each message as an SSE event.
"""

import json
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from proofhire_api.config import get_settings
from proofhire_api.db import get_db
from proofhire_api.dependencies import get_current_user
from proofhire_api.models.generation_run import GenerationRun
from proofhire_api.models.job import Job
from proofhire_api.models.sync_run import SyncRun
from proofhire_api.models.user import User

router = APIRouter(prefix="/api/v1/events", tags=["events"])

_TERMINAL_EVENTS = frozenset(
    {"generation.completed", "generation.failed", "github.sync.completed", "github.sync.failed"}
)


async def _event_stream(run_id: str):
    settings = get_settings()
    client = aioredis.from_url(settings.redis_url)
    pubsub = client.pubsub()
    await pubsub.subscribe(f"run:{run_id}")
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30.0)
            if message is None:
                yield {"event": "ping", "data": "{}"}
                continue
            payload = json.loads(message["data"])
            yield {"event": payload["event"], "data": json.dumps(payload["data"])}
            # Terminal events end the stream server-side. A GitHub sync covers
            # several repositories (one github.repo.completed each) and ends
            # with exactly one github.sync.completed / .failed.
            if payload["event"] in _TERMINAL_EVENTS:
                break
    finally:
        await pubsub.unsubscribe(f"run:{run_id}")
        await client.aclose()


@router.get("/runs/{run_id}")
async def stream_run_events(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    for model in (Job, SyncRun, GenerationRun):
        run = await db.get(model, run_id)
        if run is not None and run.user_id == current_user.id:
            return EventSourceResponse(_event_stream(str(run_id)))
    raise HTTPException(404, "Run not found")
