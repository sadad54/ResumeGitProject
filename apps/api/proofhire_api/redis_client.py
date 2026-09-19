"""Shared async Redis client, cached per event loop.

A `redis.asyncio` client owns a connection pool whose connections are bound to
the event loop that opened them. Caching one client in a module global works
only while the process has exactly one loop for its whole life — true for the
API under uvicorn, but false under TestClient (a fresh portal loop per test)
and false anywhere else that calls `asyncio.run` more than once. The symptom is
a connection error from a perfectly healthy Redis, which a fail-open caller
then swallows, silently disabling itself.

Keying the cache by the running loop keeps one pool per loop and makes the
failure mode impossible. Same root cause as the worker's NullPool fix in
apps/worker/proofhire_worker/db.py — connections must not outlive their loop.
"""

from __future__ import annotations

import asyncio

import redis.asyncio as aioredis

from proofhire_api.config import get_settings

_clients: dict[int, aioredis.Redis] = {}


def get_redis() -> aioredis.Redis:
    loop_id = id(asyncio.get_running_loop())
    client = _clients.get(loop_id)
    if client is None:
        client = aioredis.from_url(get_settings().redis_url, decode_responses=True)
        _clients[loop_id] = client
    return client
