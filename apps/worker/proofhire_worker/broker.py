"""Dramatiq + Redis broker setup.

Queues, per PRD §28 "Scale path": `ingest`, `ai`, `render`. Each maps to a
subpackage here (ingestion/, intelligence/, render/) so worker replicas can later
be scaled independently per queue.
"""

import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
broker = RedisBroker(url=redis_url)
dramatiq.set_broker(broker)
