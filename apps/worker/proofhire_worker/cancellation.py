"""Cooperative job cancellation (checklist §12.7).

Dramatiq has no safe way to kill a running actor mid-LLM-call, and killing it
would leave the job's status inconsistent anyway. So cancellation is a flag in
Redis that the long-running pipeline stages check *between* units of work — the
coverage loop checks before each requirement's rerank call, generation checks
between its stages. A cancel request therefore takes effect within one LLM
call, not instantly, and the stage that notices it is responsible for leaving
the job in a coherent `cancelled` state.

The flag expires on its own so a cancel issued for a job that never runs
doesn't linger forever.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from proofhire_api.config import get_settings

CANCEL_TTL_SECONDS = 60 * 60


class JobCancelled(Exception):
    """Raised by a pipeline stage when it observes the cancel flag."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"job {job_id} cancelled")


def _key(job_id: str) -> str:
    return f"cancel:job:{job_id}"


async def request_cancel(job_id: str) -> None:
    client = aioredis.from_url(get_settings().redis_url)
    try:
        await client.set(_key(job_id), "1", ex=CANCEL_TTL_SECONDS)
    finally:
        await client.aclose()


async def is_cancelled(job_id: str) -> bool:
    client = aioredis.from_url(get_settings().redis_url)
    try:
        return await client.exists(_key(job_id)) == 1
    finally:
        await client.aclose()


async def clear_cancel(job_id: str) -> None:
    client = aioredis.from_url(get_settings().redis_url)
    try:
        await client.delete(_key(job_id))
    finally:
        await client.aclose()


async def raise_if_cancelled(job_id: str) -> None:
    if await is_cancelled(job_id):
        raise JobCancelled(job_id)
