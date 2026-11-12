"""Where run-progress events live in Redis, shared by the worker (writer) and
the API's SSE endpoint (reader).

A capped stream per run rather than pub/sub: pub/sub drops a message nobody is
subscribed to yet, so an event published before the browser connected — a
run that failed within milliseconds, say — was lost and the browser waited
out its timeout. A stream keeps the run's events for replay; clients read
from the position their trigger request returned (`events_after`), which
also keeps events of earlier runs sharing the key (generation uses the job
id) out of the replay.
"""

STREAM_MAXLEN = 1000
STREAM_TTL_SECONDS = 24 * 3600


def run_stream_key(run_id: str) -> str:
    return f"run:{run_id}:events"
