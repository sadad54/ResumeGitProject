"""Transient-failure retry for LLM provider calls (PRD §25 "retry and rate-limit
handling").

Distinct from the providers' existing schema-repair loop: that one retries because
the *model* returned unusable content, feeding the error back into the
conversation. This one retries because the *transport* failed — 429 rate limits,
timeouts, connection drops, 5xx — where the right move is to back off and re-send
the identical request.

Vendor SDK exception types stay in the adapters: each provider passes its own
`is_retryable` predicate, so this module (and everything above it) keeps the
PRD §25 property that domain logic never imports a vendor SDK.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

MAX_ATTEMPTS = 4
BASE_DELAY_SECONDS = 0.5
MAX_DELAY_SECONDS = 20.0


def _backoff_delay(attempt: int, retry_after: float | None) -> float:
    """Exponential backoff with full jitter, floored by any server-supplied
    Retry-After. Full jitter (rather than fixed backoff) matters because every
    worker thread hits the same provider — synchronized retries would just
    recreate the burst that triggered the rate limit."""
    if retry_after is not None:
        return min(retry_after, MAX_DELAY_SECONDS)
    ceiling = min(BASE_DELAY_SECONDS * (2**attempt), MAX_DELAY_SECONDS)
    return random.uniform(0, ceiling)


def retry_after_seconds(exc: Exception) -> float | None:
    """Best-effort Retry-After extraction. Both the OpenAI and Anthropic SDKs
    surface the raw response on the exception, so this reads the header without
    importing either SDK."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


async def with_retries(
    operation: Callable[[], Awaitable[T]],
    *,
    is_retryable: Callable[[Exception], bool],
    provider: str,
    task: str,
    max_attempts: int = MAX_ATTEMPTS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Run `operation`, retrying transient failures with backoff.

    Re-raises the original exception once attempts are exhausted or the error
    isn't retryable — callers must never see a retry wrapper type, since the
    generation pipeline's own error handling keys off provider errors.
    """
    for attempt in range(max_attempts):
        try:
            return await operation()
        except Exception as exc:
            if not is_retryable(exc) or attempt == max_attempts - 1:
                raise
            delay = _backoff_delay(attempt, retry_after_seconds(exc))
            logger.warning(
                "llm_call_retrying",
                extra={
                    "provider": provider,
                    "task": task,
                    "attempt": attempt + 1,
                    "max_attempts": max_attempts,
                    "delay_seconds": round(delay, 3),
                    "error_type": type(exc).__name__,
                },
            )
            await sleep(delay)

    raise AssertionError("unreachable: loop either returns or raises")
