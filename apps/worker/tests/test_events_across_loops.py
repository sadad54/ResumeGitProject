"""publish_event works across event loops, as Dramatiq calls it: every task
runs its pipeline under its own asyncio.run(). A module-level client bound
to the first loop crashed every later task that published (found by the
first live end-to-end run)."""

import asyncio
import json
import uuid

import redis
from proofhire_contracts import RunEventName

from proofhire_worker.events import channel_name, publish_event


def test_publishing_from_successive_event_loops_delivers_every_event():
    run_id = str(uuid.uuid4())
    subscriber = redis.Redis.from_url("redis://localhost:6379/0")
    pubsub = subscriber.pubsub()
    pubsub.subscribe(channel_name(run_id))
    pubsub.get_message(timeout=1)  # subscription confirmation

    for n in range(3):  # three "tasks", three loops
        asyncio.run(publish_event(run_id, RunEventName.EVIDENCE_CREATED, {"n": n}))

    received = []
    for _ in range(3):
        message = pubsub.get_message(timeout=2)
        while message and message["type"] != "message":
            message = pubsub.get_message(timeout=2)
        assert message is not None, f"only {len(received)} of 3 events arrived"
        received.append(json.loads(message["data"])["data"]["n"])
    pubsub.close()
    assert received == [0, 1, 2]
