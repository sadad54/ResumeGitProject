"""publish_event works across event loops, as Dramatiq calls it: every task
runs its pipeline under its own asyncio.run(). A module-level client bound
to the first loop crashed every later task that published (found by the
first live end-to-end run)."""

import asyncio
import json
import uuid

import redis
from proofhire_contracts import RunEventName
from proofhire_contracts.run_events import run_stream_key

from proofhire_worker.events import publish_event


def test_publishing_from_successive_event_loops_appends_every_event():
    run_id = str(uuid.uuid4())
    for n in range(3):  # three "tasks", three loops
        asyncio.run(publish_event(run_id, RunEventName.EVIDENCE_CREATED, {"n": n}))

    client = redis.Redis.from_url("redis://localhost:6379/0", decode_responses=True)
    key = run_stream_key(run_id)
    try:
        entries = client.xrange(key)
        assert [json.loads(f["payload"])["data"]["n"] for _id, f in entries] == [0, 1, 2]
        assert 0 < client.ttl(key) <= 24 * 3600, "streams must expire, not accumulate"
    finally:
        client.delete(key)
