"""SSE run-progress stream (PRD §23 "Streaming": SSE before WebSockets, ADR-0008).

Subscribes to the same Redis pub/sub channel the worker publishes to
(proofhire_worker/events.py) and forwards each message as an SSE event.
"""

import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from proofhire_api.config import get_settings
from proofhire_api.dependencies import get_current_user_sse
from proofhire_api.models.user import User

router = APIRouter(prefix="/api/v1/events", tags=["events"])


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
            # Terminal events that end the stream server-side. GitHub sync has no
            # single terminal event (a run may cover several repos, each emitting
            # its own github.repo.completed) — the client tracks completion against
            # the repository_ids it received from POST /github/sync and closes the
            # EventSource itself, or falls back to GET /github/sync/{run_id}.
            if payload["event"] in {"generation.completed", "generation.failed"}:
                break
    finally:
        await pubsub.unsubscribe(f"run:{run_id}")
        await client.aclose()


@router.get("/runs/{run_id}")
async def stream_run_events(run_id: str, _current_user: User = Depends(get_current_user_sse)):
    return EventSourceResponse(_event_stream(run_id))
