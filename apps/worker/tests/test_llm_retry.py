"""Tests for transient-failure retry on LLM provider calls (PRD §25)."""

import pytest

from proofhire_worker.intelligence.retry import retry_after_seconds, with_retries


class _Boom(Exception):
    pass


class _Fatal(Exception):
    pass


def _retryable(exc: Exception) -> bool:
    return isinstance(exc, _Boom)


async def _no_sleep(_seconds: float) -> None:
    return None


async def test_succeeds_without_retrying_when_the_call_works():
    calls = []

    async def operation():
        calls.append(1)
        return "ok"

    result = await with_retries(
        operation, is_retryable=_retryable, provider="test", task="t", sleep=_no_sleep
    )

    assert result == "ok"
    assert len(calls) == 1


async def test_retries_transient_failures_then_succeeds():
    attempts = []

    async def operation():
        attempts.append(1)
        if len(attempts) < 3:
            raise _Boom("429")
        return "recovered"

    result = await with_retries(
        operation, is_retryable=_retryable, provider="test", task="t", sleep=_no_sleep
    )

    assert result == "recovered"
    assert len(attempts) == 3


async def test_gives_up_after_max_attempts_and_reraises_original_error():
    attempts = []

    async def operation():
        attempts.append(1)
        raise _Boom("still rate limited")

    with pytest.raises(_Boom):
        await with_retries(
            operation,
            is_retryable=_retryable,
            provider="test",
            task="t",
            max_attempts=3,
            sleep=_no_sleep,
        )

    assert len(attempts) == 3


async def test_non_retryable_error_fails_immediately_without_burning_attempts():
    """A bad API key or malformed request must not be retried — retrying a
    deterministic failure just wastes quota and delays the real error."""
    attempts = []

    async def operation():
        attempts.append(1)
        raise _Fatal("invalid api key")

    with pytest.raises(_Fatal):
        await with_retries(
            operation, is_retryable=_retryable, provider="test", task="t", sleep=_no_sleep
        )

    assert len(attempts) == 1


async def test_server_supplied_retry_after_is_used_as_the_delay():
    slept: list[float] = []

    class _Headers(dict):
        pass

    class _Response:
        headers = {"retry-after": "7"}

    exc = _Boom("429")
    exc.response = _Response()

    attempts = []

    async def operation():
        attempts.append(1)
        if len(attempts) == 1:
            raise exc
        return "ok"

    async def record_sleep(seconds: float) -> None:
        slept.append(seconds)

    await with_retries(
        operation, is_retryable=_retryable, provider="test", task="t", sleep=record_sleep
    )

    assert slept == [7.0]


def test_retry_after_returns_none_when_header_is_absent_or_unparseable():
    assert retry_after_seconds(_Boom("no response attached")) is None

    class _Response:
        headers = {"retry-after": "soon"}

    exc = _Boom("bad header")
    exc.response = _Response()
    assert retry_after_seconds(exc) is None
