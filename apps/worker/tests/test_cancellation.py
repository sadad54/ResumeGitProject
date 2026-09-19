"""Cooperative cancellation (checklist §12.7): the flag round-trips through
real Redis, and the coverage loop stops at the next check with the job left
in a coherent `cancelled` state instead of half-computed."""

import uuid

import pytest
from proofhire_contracts import RequirementCategory
from sqlalchemy import select

from proofhire_api.db import async_session_factory
from proofhire_api.models.job import Job
from proofhire_api.models.requirement import Requirement
from proofhire_api.models.user import User
from proofhire_api.security.password import hash_password
from proofhire_worker import cancellation
from proofhire_worker.intelligence import coverage


async def test_cancel_flag_round_trips_and_clears():
    job_id = str(uuid.uuid4())
    assert not await cancellation.is_cancelled(job_id)
    await cancellation.request_cancel(job_id)
    assert await cancellation.is_cancelled(job_id)
    await cancellation.clear_cancel(job_id)
    assert not await cancellation.is_cancelled(job_id)


async def test_raise_if_cancelled_raises_only_when_flagged():
    job_id = str(uuid.uuid4())
    await cancellation.raise_if_cancelled(job_id)  # no flag: no raise
    await cancellation.request_cancel(job_id)
    with pytest.raises(cancellation.JobCancelled):
        await cancellation.raise_if_cancelled(job_id)
    await cancellation.clear_cancel(job_id)


async def test_coverage_loop_stops_and_marks_job_cancelled(monkeypatch):
    """The loop must not call the reranker at all once the flag is set, and
    must leave status=cancelled rather than ready/coverage_failed."""
    calls = {"rerank": 0}

    class _Provider:
        async def structured_generate(self, **_kw):
            calls["rerank"] += 1
            raise AssertionError("reranker must not run after cancel")

    class _Embedder:
        async def embed(self, texts, *, model):
            return [[0.0] * 1536 for _ in texts]

    monkeypatch.setattr(coverage, "get_provider", lambda: _Provider())
    monkeypatch.setattr(coverage, "get_embedding_provider", lambda: _Embedder())

    async with async_session_factory() as session:
        user = User(email=f"cancel-{uuid.uuid4().hex[:8]}@example.com", hashed_password=hash_password("x"))
        session.add(user)
        await session.flush()
        job = Job(user_id=user.id, source_text="jd", status="matching")
        session.add(job)
        await session.flush()
        for i in range(3):
            session.add(Requirement(job_id=job.id, category=RequirementCategory.SKILL, text=f"req {i}",
                                    normalized=[], importance=0.5, required=True))
        await session.commit()
        job_id = str(job.id)
        user_id = user.id

    await cancellation.request_cancel(job_id)
    try:
        await coverage._compute_coverage(job_id)

        async with async_session_factory() as session:
            refreshed = await session.scalar(select(Job).where(Job.id == uuid.UUID(job_id)))
            assert refreshed.status == "cancelled"
        assert calls["rerank"] == 0
        assert not await cancellation.is_cancelled(job_id), "flag should be cleared once observed"
    finally:
        await cancellation.clear_cancel(job_id)
        async with async_session_factory() as session:
            await session.delete(await session.get(User, user_id))
            await session.commit()
