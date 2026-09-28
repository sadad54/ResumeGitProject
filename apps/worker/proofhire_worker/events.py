"""Publishes run-progress events to Redis pub/sub. The API's SSE endpoint
(GET /api/v1/events/runs/{run_id}) subscribes to the same channel and forwards
messages to connected clients (PRD §23 "Streaming").

A fresh client per publish, like embedding_cache.py and cancellation.py: every
Dramatiq task runs its pipeline under its own asyncio.run(), so a client
cached at module level carries connections bound to the first task's event
loop into every later task. The first live end-to-end run crashed extraction
on exactly that ("Future attached to a different loop", then "Event loop is
closed") as soon as it published after a sync. A localhost connection per
event costs well under a millisecond; a task publishes tens of events at most.
"""

import json
import os
from datetime import UTC, datetime

import redis.asyncio as aioredis
from proofhire_contracts import RunEventName

_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def channel_name(run_id: str) -> str:
    return f"run:{run_id}"


async def publish_event(run_id: str, event: RunEventName, data: dict) -> None:
    payload = {
        "event": event.value,
        "data": data,
        "ts": datetime.now(UTC).isoformat(),
    }
    client = aioredis.from_url(_redis_url)
    try:
        await client.publish(channel_name(run_id), json.dumps(payload))
    finally:
        await client.aclose()
