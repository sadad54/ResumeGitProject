"""Publishes run-progress events to the run's Redis stream. The API's SSE
endpoint (GET /api/v1/events/runs/{run_id}) reads the same stream and
forwards entries to connected clients (PRD §23 "Streaming"); see
proofhire_contracts.run_events for why a stream rather than pub/sub.

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
from proofhire_contracts.run_events import STREAM_MAXLEN, STREAM_TTL_SECONDS, run_stream_key

_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


async def publish_event(run_id: str, event: RunEventName, data: dict) -> None:
    payload = {
        "event": event.value,
        "data": data,
        "ts": datetime.now(UTC).isoformat(),
    }
    key = run_stream_key(run_id)
    client = aioredis.from_url(_redis_url)
    try:
        async with client.pipeline(transaction=False) as pipe:
            pipe.xadd(key, {"payload": json.dumps(payload)}, maxlen=STREAM_MAXLEN, approximate=True)
            pipe.expire(key, STREAM_TTL_SECONDS)
            await pipe.execute()
    finally:
        await client.aclose()
