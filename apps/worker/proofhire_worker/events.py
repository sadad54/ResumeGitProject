"""Publishes run-progress events to Redis pub/sub. The API's SSE endpoint
(GET /api/v1/events/runs/{run_id}) subscribes to the same channel and forwards
messages to connected clients (PRD §23 "Streaming").
"""

import json
import os
from datetime import datetime, timezone

import redis.asyncio as aioredis
from proofhire_contracts import RunEventName

_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_client: aioredis.Redis | None = None


def _get_client() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(_redis_url)
    return _client


def channel_name(run_id: str) -> str:
    return f"run:{run_id}"


async def publish_event(run_id: str, event: RunEventName, data: dict) -> None:
    payload = {
        "event": event.value,
        "data": data,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    await _get_client().publish(channel_name(run_id), json.dumps(payload))
