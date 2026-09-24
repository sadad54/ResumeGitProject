"""Rate limiting tests (PRD §27). Exercises the real Redis-backed counter rather
than a mock, since the whole point of the Redis backing is behavior a mock
wouldn't reproduce (shared counter, TTL-based window, fail-open)."""

import uuid

import pytest

from proofhire_api.security import rate_limit as rl


@pytest.fixture
def bucket() -> str:
    return f"ratelimit:test:{uuid.uuid4()}"


async def test_allows_requests_up_to_the_limit_then_blocks(bucket):
    allowed = [await rl._consume(bucket, limit=3, window_seconds=60) for _ in range(3)]
    assert allowed == [None, None, None]

    blocked = await rl._consume(bucket, limit=3, window_seconds=60)
    assert blocked is not None and blocked > 0


async def test_separate_buckets_have_independent_budgets(bucket):
    other = f"{bucket}-other"
    for _ in range(3):
        await rl._consume(bucket, limit=3, window_seconds=60)

    assert await rl._consume(bucket, limit=3, window_seconds=60) is not None
    assert await rl._consume(other, limit=3, window_seconds=60) is None


async def test_fails_open_when_redis_is_unavailable(monkeypatch, bucket):
    """A degraded rate-limit backend must not take the API down with it."""

    class _Broken:
        async def incr(self, _key):
            raise ConnectionError("redis down")

    monkeypatch.setattr(rl, "get_redis", lambda: _Broken())

    assert await rl._consume(bucket, limit=1, window_seconds=60) is None


async def test_global_rate_limit_shares_one_budget_across_callers(monkeypatch, bucket):
    """Unlike RateLimit, GlobalRateLimit has no user to key by (it guards the
    unauthenticated demo/session endpoint) — every caller draws from the same
    bucket by name."""
    import fastapi

    limiter = rl.GlobalRateLimit(name=bucket.removeprefix("ratelimit:"), limit=2, window_seconds=60)

    await limiter()
    await limiter()
    with pytest.raises(fastapi.HTTPException) as exc_info:
        await limiter()
    assert exc_info.value.status_code == 429
