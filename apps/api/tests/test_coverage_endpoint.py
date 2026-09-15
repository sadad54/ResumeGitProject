"""Integration test against the real DB — calls the get_coverage route function
directly (bypassing FastAPI's dependency injection, which isn't needed here)
to verify the Evidence Coverage Matrix's implicit-Gap and populated-match rows
(PRD §18)."""

import uuid

import pytest
from proofhire_contracts import EvidenceType, MatchLabel, RequirementCategory
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import async_session_factory
from proofhire_api.models.evidence_match import EvidenceMatch
from proofhire_api.models.job import Job
from proofhire_api.models.repository import Repository
from proofhire_api.models.requirement import Requirement
from proofhire_api.models.source_artifact import SourceArtifact
from proofhire_api.models.user import User
from proofhire_api.repositories.evidence import (
    EvidenceCandidate,
    EvidenceSourceCandidate,
    SQLAlchemyEvidenceRepository,
)
from proofhire_api.routers.jobs import get_coverage
from proofhire_api.security.password import hash_password


@pytest.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def fixture_env(db_session: AsyncSession):
    user = User(
        email=f"coverage-test-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("irrelevant"),
    )
    db_session.add(user)
    await db_session.flush()

    repo = Repository(
        user_id=user.id,
        provider_repo_id=int.from_bytes(uuid.uuid4().bytes[:4], "big") % 2_000_000_000,
        owner="testowner",
        name="testrepo",
        url="https://github.com/testowner/testrepo",
    )
    db_session.add(repo)
    await db_session.flush()

    artifact = SourceArtifact(
        repository_id=repo.id, type="source_file", path="app/main.py",
        commit_sha="a" * 40, content_hash="b" * 64, priority="p1",
    )
    db_session.add(artifact)
    await db_session.flush()

    job = Job(user_id=user.id, source_text="fixture JD")
    db_session.add(job)
    await db_session.flush()
    await db_session.commit()

    yield user, repo, artifact, job

    async with async_session_factory() as cleanup_session:
        await cleanup_session.delete(await cleanup_session.get(User, user.id))
        await cleanup_session.commit()


@pytest.mark.asyncio
async def test_requirement_without_match_is_implicit_gap(db_session, fixture_env):
    user, _repo, _artifact, job = fixture_env
    requirement = Requirement(
        job_id=job.id, category=RequirementCategory.SKILL, text="5+ years Kubernetes",
        normalized=["kubernetes"], importance=0.9, required=True,
    )
    db_session.add(requirement)
    await db_session.commit()

    rows = await get_coverage(job.id, current_user=user, db=db_session)

    assert len(rows) == 1
    assert rows[0].match_label == MatchLabel.GAP
    assert rows[0].evidence_id is None
    assert "No candidate evidence" in rows[0].explanation


@pytest.mark.asyncio
async def test_requirement_with_persisted_match_shows_evidence_and_repository(db_session, fixture_env):
    user, repo, artifact, job = fixture_env
    requirement = Requirement(
        job_id=job.id, category=RequirementCategory.SKILL, text="FastAPI experience",
        normalized=["fastapi"], importance=0.8, required=True,
    )
    db_session.add(requirement)
    await db_session.flush()

    evidence_repo = SQLAlchemyEvidenceRepository(db_session)
    [evidence] = await evidence_repo.save_candidates(
        [
            EvidenceCandidate(
                user_id=user.id, repository_id=repo.id, evidence_type=EvidenceType.SKILL_USAGE,
                title="Uses FastAPI", normalized_claim="Builds APIs with FastAPI.",
                description="", confidence=0.9, extraction_method="test",
                sources=[EvidenceSourceCandidate(
                    source_artifact_id=artifact.id, locator="app/main.py",
                    snippet_hash="d" * 64, commit_sha="a" * 40,
                )],
            )
        ]
    )

    db_session.add(
        EvidenceMatch(
            requirement_id=requirement.id, evidence_id=evidence.id,
            retrieval_score=0.9, rerank_score=0.85,
            match_reason="Directly demonstrates FastAPI usage.", status=MatchLabel.STRONG,
        )
    )
    await db_session.commit()

    rows = await get_coverage(job.id, current_user=user, db=db_session)

    assert len(rows) == 1
    row = rows[0]
    assert row.match_label == MatchLabel.STRONG
    assert row.evidence_title == "Uses FastAPI"
    assert row.evidence_repository == "testowner/testrepo"
    assert row.action == "Include in resume"
