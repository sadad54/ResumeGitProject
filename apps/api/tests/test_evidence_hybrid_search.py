"""Integration test against the real DB for the ADR-0006 fusion query. Uses
embedding=None throughout to isolate the lexical + skill-overlap signals (the
vector term's optional-branch is exercised implicitly by every call here, since
has_embedding=False skips it entirely — a separate concern from ranking
correctness, which doesn't need real semantic embeddings to verify)."""

import uuid

import pytest
from proofhire_contracts import EvidenceType
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import async_session_factory
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


@pytest.fixture
async def fixture_env(db_session: AsyncSession):
    user = User(
        email=f"hybrid-test-{uuid.uuid4().hex[:8]}@example.com",
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

    async with async_session_factory() as cleanup_session:
        await cleanup_session.delete(await cleanup_session.get(User, user.id))
        await cleanup_session.commit()


def _source(artifact) -> EvidenceSourceCandidate:
    return EvidenceSourceCandidate(
        source_artifact_id=artifact.id, locator="app/main.py", snippet_hash="c" * 64, commit_sha="a" * 40
    )


@pytest.mark.asyncio
async def test_lexical_match_outranks_unrelated_evidence(db_session, fixture_env):
    user, repo, artifact = fixture_env
    repo_layer = SQLAlchemyEvidenceRepository(db_session)

    await repo_layer.save_candidates(
        [
            EvidenceCandidate(
                user_id=user.id, repository_id=repo.id, evidence_type=EvidenceType.SKILL_USAGE,
                title="Kafka producer", normalized_claim="Implements a Kafka producer for event streaming.",
                description="", confidence=0.8, extraction_method="test", sources=[_source(artifact)],
            ),
            EvidenceCandidate(
                user_id=user.id, repository_id=repo.id, evidence_type=EvidenceType.SKILL_USAGE,
                title="CSS styling", normalized_claim="Writes CSS with Tailwind utility classes.",
                description="", confidence=0.8, extraction_method="test", sources=[_source(artifact)],
            ),
        ]
    )

    hits = await repo_layer.hybrid_search(EvidenceQuery(user_id=user.id, text="Kafka streaming", limit=5))

    assert len(hits) >= 1
    assert hits[0].title == "Kafka producer"
    assert hits[0].lexical_score > 0


@pytest.mark.asyncio
async def test_skill_overlap_boosts_matching_evidence_above_lexical_only(db_session, fixture_env):
    user, repo, artifact = fixture_env
    repo_layer = SQLAlchemyEvidenceRepository(db_session)

    # Both mention "database" in text, but only one is actually tagged with the
    # postgresql skill — skill overlap should help it win even with similar text.
    await repo_layer.save_candidates(
        [
            EvidenceCandidate(
                user_id=user.id, repository_id=repo.id, evidence_type=EvidenceType.SKILL_USAGE,
                title="Generic database usage", normalized_claim="Uses a database for persistence.",
                description="", confidence=0.8, extraction_method="test", sources=[_source(artifact)],
                skill_names=[],
            ),
            EvidenceCandidate(
                user_id=user.id, repository_id=repo.id, evidence_type=EvidenceType.SKILL_USAGE,
                title="PostgreSQL usage", normalized_claim="Connects to a database for persistence.",
                description="", confidence=0.8, extraction_method="test", sources=[_source(artifact)],
                skill_names=["postgresql"],
            ),
        ]
    )

    hits = await repo_layer.hybrid_search(
        EvidenceQuery(user_id=user.id, text="database persistence", skill_keywords=["postgresql"], limit=5)
    )

    assert hits[0].title == "PostgreSQL usage"
    assert hits[0].skill_score > 0


@pytest.mark.asyncio
async def test_hybrid_search_excludes_rejected_evidence(db_session, fixture_env):
    user, repo, artifact = fixture_env
    repo_layer = SQLAlchemyEvidenceRepository(db_session)

    saved = await repo_layer.save_candidates(
        [
            EvidenceCandidate(
                user_id=user.id, repository_id=repo.id, evidence_type=EvidenceType.SKILL_USAGE,
                title="Redis caching", normalized_claim="Uses Redis for caching layer.",
                description="", confidence=0.8, extraction_method="test", sources=[_source(artifact)],
            ),
        ]
    )
    saved[0].status = "rejected"
    await db_session.commit()

    hits = await repo_layer.hybrid_search(EvidenceQuery(user_id=user.id, text="Redis caching", limit=5))
    assert hits == []


@pytest.mark.asyncio
async def test_hybrid_search_scopes_by_user(db_session, fixture_env):
    user, repo, artifact = fixture_env
    other_user = User(
        email=f"hybrid-other-{uuid.uuid4().hex[:8]}@example.com", hashed_password=hash_password("x")
    )
    db_session.add(other_user)
    await db_session.flush()
    await db_session.commit()

    repo_layer = SQLAlchemyEvidenceRepository(db_session)
    await repo_layer.save_candidates(
        [
            EvidenceCandidate(
                user_id=user.id, repository_id=repo.id, evidence_type=EvidenceType.SKILL_USAGE,
                title="GraphQL API", normalized_claim="Builds a GraphQL API layer.",
                description="", confidence=0.8, extraction_method="test", sources=[_source(artifact)],
            ),
        ]
    )

    hits = await repo_layer.hybrid_search(EvidenceQuery(user_id=other_user.id, text="GraphQL API", limit=5))
    assert hits == []

    await db_session.delete(other_user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_evidence_type_metadata_filter_narrows_candidates(db_session, fixture_env):
    """Metadata filtering (PRD §17) must exclude non-matching types entirely,
    not merely rank them lower — a filtered-out type should not appear at all
    even when it is the strongest lexical match."""
    user, repo, artifact = fixture_env
    repo_layer = SQLAlchemyEvidenceRepository(db_session)

    await repo_layer.save_candidates(
        [
            EvidenceCandidate(
                user_id=user.id, repository_id=repo.id, evidence_type=EvidenceType.SKILL_USAGE,
                title="Terraform modules", normalized_claim="Authors Terraform modules for infrastructure.",
                description="", confidence=0.8, extraction_method="test", sources=[_source(artifact)],
            ),
            EvidenceCandidate(
                user_id=user.id, repository_id=repo.id, evidence_type=EvidenceType.ARCHITECTURE,
                title="Terraform state backend", normalized_claim="Chose a remote Terraform state backend.",
                description="", confidence=0.8, extraction_method="test", sources=[_source(artifact)],
            ),
        ]
    )

    unfiltered = await repo_layer.hybrid_search(
        EvidenceQuery(user_id=user.id, text="Terraform", limit=10)
    )
    assert {h.title for h in unfiltered} >= {"Terraform modules", "Terraform state backend"}

    filtered = await repo_layer.hybrid_search(
        EvidenceQuery(
            user_id=user.id,
            text="Terraform",
            limit=10,
            evidence_types=[EvidenceType.ARCHITECTURE.value],
        )
    )
    assert [h.title for h in filtered] == ["Terraform state backend"]


@pytest.mark.asyncio
async def test_repository_metadata_filter_excludes_other_repositories(db_session, fixture_env):
    user, repo, artifact = fixture_env
    other_repo = Repository(
        user_id=user.id,
        provider_repo_id=int.from_bytes(uuid.uuid4().bytes[:4], "big") % 2_000_000_000,
        owner="testowner",
        name="otherrepo",
        url="https://github.com/testowner/otherrepo",
    )
    db_session.add(other_repo)
    await db_session.flush()

    other_artifact = SourceArtifact(
        repository_id=other_repo.id, type="source_file", path="svc/api.py",
        commit_sha="d" * 40, content_hash="e" * 64, priority="p1",
    )
    db_session.add(other_artifact)
    await db_session.flush()
    await db_session.commit()

    repo_layer = SQLAlchemyEvidenceRepository(db_session)
    await repo_layer.save_candidates(
        [
            EvidenceCandidate(
                user_id=user.id, repository_id=repo.id, evidence_type=EvidenceType.SKILL_USAGE,
                title="gRPC service in repo A", normalized_claim="Implements a gRPC service.",
                description="", confidence=0.8, extraction_method="test", sources=[_source(artifact)],
            ),
            EvidenceCandidate(
                user_id=user.id, repository_id=other_repo.id, evidence_type=EvidenceType.SKILL_USAGE,
                title="gRPC service in repo B", normalized_claim="Implements a gRPC service.",
                description="", confidence=0.8, extraction_method="test",
                sources=[
                    EvidenceSourceCandidate(
                        source_artifact_id=other_artifact.id, locator="svc/api.py",
                        snippet_hash="f" * 64, commit_sha="d" * 40,
                    )
                ],
            ),
        ]
    )

    filtered = await repo_layer.hybrid_search(
        EvidenceQuery(user_id=user.id, text="gRPC service", limit=10, repository_ids=[other_repo.id])
    )
    assert [h.title for h in filtered] == ["gRPC service in repo B"]
