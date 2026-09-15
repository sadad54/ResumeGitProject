"""Integration test against a real Postgres+pgvector database (not mocked) —
verifies EvidenceRepository.save_candidates actually persists provenance
correctly, enforces the "no sources -> dropped" rule (PRD §14), and that
hybrid_search finds what was saved. Requires DATABASE_URL to point at a real,
migrated database (see README's local dev setup).
"""

import uuid

import pytest
from proofhire_contracts import EvidenceStatus, EvidenceType
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import async_session_factory
from proofhire_api.models.github_connection import GitHubConnection
from proofhire_api.models.repository import Repository
from proofhire_api.models.source_artifact import SourceArtifact
from proofhire_api.models.user import User
from proofhire_api.repositories.evidence import (
    EvidenceCandidate,
    EvidenceQuery,
    EvidenceSourceCandidate,
    SQLAlchemyEvidenceRepository,
)
from proofhire_api.security.password import hash_password


@pytest.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def fixture_repo(db_session: AsyncSession):
    """Creates a throwaway user/repository/source_artifact, cleaned up after."""
    user = User(
        email=f"evidence-test-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("irrelevant"),
    )
    db_session.add(user)
    await db_session.flush()

    repo = Repository(
        user_id=user.id,
        # Postgres INTEGER is 32-bit signed; mask so this stays in range.
        provider_repo_id=int.from_bytes(uuid.uuid4().bytes[:4], "big") % 2_000_000_000,
        owner="testowner",
        name="testrepo",
        url="https://github.com/testowner/testrepo",
    )
    db_session.add(repo)
    await db_session.flush()

    artifact = SourceArtifact(
        repository_id=repo.id,
        type="source_file",
        path="app/main.py",
        commit_sha="a" * 40,
        content_hash="b" * 64,
        priority="p1",
    )
    db_session.add(artifact)
    await db_session.flush()
    await db_session.commit()

    yield user, repo, artifact

    # Cleanup — cascades delete evidence/sources/repo via FK ondelete=CASCADE.
    async with async_session_factory() as cleanup_session:
        await cleanup_session.delete(await cleanup_session.get(User, user.id))
        await cleanup_session.commit()


@pytest.mark.asyncio
async def test_save_candidates_persists_evidence_with_provenance(db_session, fixture_repo):
    user, repo, artifact = fixture_repo
    repository = SQLAlchemyEvidenceRepository(db_session)

    candidates = [
        EvidenceCandidate(
            user_id=user.id,
            repository_id=repo.id,
            evidence_type=EvidenceType.SKILL_USAGE,
            title="Uses FastAPI",
            normalized_claim="The repository uses FastAPI for its HTTP API layer.",
            description="app/main.py imports and configures a FastAPI application.",
            confidence=0.9,
            extraction_method="evidence_extract:v1",
            sources=[
                EvidenceSourceCandidate(
                    source_artifact_id=artifact.id,
                    locator="app/main.py",
                    snippet_hash="c" * 64,
                    commit_sha="a" * 40,
                )
            ],
            skill_names=["fastapi"],
        )
    ]

    saved = await repository.save_candidates(candidates)
    assert len(saved) == 1
    assert saved[0].status == EvidenceStatus.CANDIDATE
    assert saved[0].title == "Uses FastAPI"


@pytest.mark.asyncio
async def test_save_candidates_drops_items_without_sources(db_session, fixture_repo):
    user, repo, _artifact = fixture_repo
    repository = SQLAlchemyEvidenceRepository(db_session)

    candidates = [
        EvidenceCandidate(
            user_id=user.id,
            repository_id=repo.id,
            evidence_type=EvidenceType.FEATURE,
            title="Unsourced claim",
            normalized_claim="This has no provenance and must be dropped.",
            description="",
            confidence=0.5,
            extraction_method="evidence_extract:v1",
            sources=[],  # PRD §14: no source -> not persisted
        )
    ]

    saved = await repository.save_candidates(candidates)
    assert saved == []


@pytest.mark.asyncio
async def test_save_candidates_deduplicates_identical_claims(db_session, fixture_repo):
    user, repo, artifact = fixture_repo
    repository = SQLAlchemyEvidenceRepository(db_session)

    def make_candidate():
        return EvidenceCandidate(
            user_id=user.id,
            repository_id=repo.id,
            evidence_type=EvidenceType.SKILL_USAGE,
            title="Uses Docker",
            normalized_claim="The repository is containerized with Docker.",
            description="A Dockerfile is present at the repo root.",
            confidence=0.8,
            extraction_method="evidence_extract:v1",
            sources=[
                EvidenceSourceCandidate(
                    source_artifact_id=artifact.id,
                    locator="Dockerfile",
                    snippet_hash="d" * 64,
                    commit_sha="a" * 40,
                )
            ],
        )

    first = await repository.save_candidates([make_candidate()])
    second = await repository.save_candidates([make_candidate()])
    assert len(first) == 1
    assert second == []  # exact duplicate claim for the same repo is a no-op


@pytest.mark.asyncio
async def test_hybrid_search_finds_saved_evidence(db_session, fixture_repo):
    user, repo, artifact = fixture_repo
    repository = SQLAlchemyEvidenceRepository(db_session)

    await repository.save_candidates(
        [
            EvidenceCandidate(
                user_id=user.id,
                repository_id=repo.id,
                evidence_type=EvidenceType.SKILL_USAGE,
                title="Uses PostgreSQL",
                normalized_claim="The repository connects to a PostgreSQL database.",
                description="",
                confidence=0.85,
                extraction_method="evidence_extract:v1",
                sources=[
                    EvidenceSourceCandidate(
                        source_artifact_id=artifact.id,
                        locator="app/db.py",
                        snippet_hash="e" * 64,
                        commit_sha="a" * 40,
                    )
                ],
            )
        ]
    )

    hits = await repository.hybrid_search(
        EvidenceQuery(user_id=user.id, text="PostgreSQL", limit=5)
    )
    assert len(hits) == 1
    assert hits[0].title == "Uses PostgreSQL"

    no_hits = await repository.hybrid_search(
        EvidenceQuery(user_id=user.id, text="nonexistent-technology-xyz", limit=5)
    )
    assert no_hits == []
