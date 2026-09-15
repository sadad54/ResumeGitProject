"""Integration test against the real DB — verifies JobRepository.save_analysis
fills role/company/seniority only when unset, and dedups exact-text requirements
across re-analysis runs."""

import uuid

import pytest
from proofhire_contracts import RequirementCategory
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import async_session_factory
from proofhire_api.models.job import Job
from proofhire_api.models.user import User
from proofhire_api.repositories.job import (
    JobAnalysisResult,
    RequirementCandidate,
    SQLAlchemyJobRepository,
)
from proofhire_api.security.password import hash_password


@pytest.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def fixture_job(db_session: AsyncSession):
    user = User(
        email=f"job-test-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("irrelevant"),
    )
    db_session.add(user)
    await db_session.flush()

    job = Job(user_id=user.id, source_text="Backend Engineer role...")
    db_session.add(job)
    await db_session.flush()
    await db_session.commit()

    yield job

    async with async_session_factory() as cleanup_session:
        await cleanup_session.delete(await cleanup_session.get(User, user.id))
        await cleanup_session.commit()


def _candidate(text="2+ years of Python") -> RequirementCandidate:
    return RequirementCandidate(
        category=RequirementCategory.SKILL,
        text=text,
        normalized=["python"],
        importance=0.8,
        required=True,
    )


@pytest.mark.asyncio
async def test_save_analysis_populates_job_metadata(db_session, fixture_job):
    repo = SQLAlchemyJobRepository(db_session)
    result = JobAnalysisResult(role="Backend Engineer", company="Acme", seniority="mid", requirements=[_candidate()])

    saved = await repo.save_analysis(fixture_job.id, result)

    assert len(saved) == 1
    refreshed = await db_session.get(Job, fixture_job.id)
    assert refreshed.role == "Backend Engineer"
    assert refreshed.company == "Acme"
    assert refreshed.status == "analyzed"


@pytest.mark.asyncio
async def test_save_analysis_does_not_overwrite_existing_metadata(db_session, fixture_job):
    fixture_job.role = "User-Specified Role"
    await db_session.commit()

    repo = SQLAlchemyJobRepository(db_session)
    await repo.save_analysis(
        fixture_job.id,
        JobAnalysisResult(role="LLM-Guessed Role", company=None, seniority=None, requirements=[]),
    )

    refreshed = await db_session.get(Job, fixture_job.id)
    assert refreshed.role == "User-Specified Role"


@pytest.mark.asyncio
async def test_save_analysis_dedups_identical_requirement_text_on_reanalysis(db_session, fixture_job):
    repo = SQLAlchemyJobRepository(db_session)

    first = await repo.save_analysis(
        fixture_job.id, JobAnalysisResult(role=None, company=None, seniority=None, requirements=[_candidate()])
    )
    second = await repo.save_analysis(
        fixture_job.id, JobAnalysisResult(role=None, company=None, seniority=None, requirements=[_candidate()])
    )

    assert len(first) == 1
    assert second == []  # identical text already exists — no duplicate row


@pytest.mark.asyncio
async def test_save_analysis_raises_for_unknown_job(db_session):
    repo = SQLAlchemyJobRepository(db_session)
    with pytest.raises(ValueError):
        await repo.save_analysis(
            uuid.uuid4(), JobAnalysisResult(role=None, company=None, seniority=None, requirements=[])
        )
