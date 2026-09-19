"""Redis-backed rate limiting (PRD §27).

Backed by Redis rather than process memory because the API is designed to run as
multiple replicas (infra/deployment/README.md) — an in-memory counter would give
each replica its own independent budget, so an N-replica deployment would silently
allow N times the intended rate.

Fixed-window counters: one INCR plus an EXPIRE on first write, which is a single
round trip and needs no stored timestamps. The tradeoff is the usual
fixed-window burst at a boundary (up to 2x the limit across two adjacent
windows). That is acceptable here because these limits exist to bound cost and
abuse of expensive LLM/GitHub-backed endpoints, not to enforce a precise
contractual quota.

Fails open: if Redis is unreachable the request proceeds. A rate limiter that
takes the whole API down when its own dependency is degraded causes a worse
outage than the abuse it prevents.
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, status

from proofhire_api.dependencies import get_current_user
from proofhire_api.models.user import User
from proofhire_api.redis_client import get_redis

logger = logging.getLogger(__name__)


async def _consume(bucket: str, limit: int, window_seconds: int) -> int | None:
    """Increment the window counter. Returns seconds-to-reset when over the
    limit, None when the request is allowed (or when Redis is unavailable)."""
    try:
        client = get_redis()
        count = await client.incr(bucket)
        if count == 1:
            await client.expire(bucket, window_seconds)
        if count > limit:
            ttl = await client.ttl(bucket)
            return ttl if ttl and ttl > 0 else window_seconds
        return None
    except Exception:
        logger.warning("rate_limit_backend_unavailable", extra={"bucket": bucket})
        return None


class RateLimit:
    """Per-user rate limit for a named operation.

    Keyed by user id (not IP): these endpoints all require authentication, and
    every expensive downstream cost — LLM tokens, GitHub API quota — is incurred
    per user account, so that is the budget worth bounding. IP keying would also
    wrongly collapse users behind a shared NAT into one budget.
    """

    def __init__(self, *, name: str, limit: int, window_seconds: int) -> None:
        self.name = name
        self.limit = limit
        self.window_seconds = window_seconds

    async def __call__(self, user: User = Depends(get_current_user)) -> None:
        bucket = f"ratelimit:{self.name}:{user.id}"
        retry_after = await _consume(bucket, self.limit, self.window_seconds)
        if retry_after is not None:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Rate limit exceeded. Try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )


# Tightest limits guard the endpoints that spend real money or third-party quota
# on each call; list/read endpoints are left unlimited since they are cheap and
# already ownership-scoped.
analyze_rate_limit = RateLimit(name="job_analyze", limit=10, window_seconds=60)
generate_rate_limit = RateLimit(name="generate", limit=10, window_seconds=60)
sync_rate_limit = RateLimit(name="github_sync", limit=5, window_seconds=300)
export_rate_limit = RateLimit(name="export", limit=20, window_seconds=60)
