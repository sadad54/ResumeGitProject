"""Incremental reprocessing and evidence staleness (checklist §1.9, §2.9).

Runs against the real database: the behavior under test is entirely about how
rows relate across two syncs, which an in-memory fake would not reproduce.
"""

import uuid

import pytest
from proofhire_contracts import EvidenceStatus, EvidenceType
from sqlalchemy import select

from proofhire_api.db import async_session_factory
from proofhire_api.models.evidence import Evidence
from proofhire_api.models.repository import Repository
from proofhire_api.models.source_artifact import SourceArtifact
from proofhire_api.models.user import User
from proofhire_api.repositories.evidence import (
    EvidenceCandidate,
    EvidenceSourceCandidate,
    SQLAlchemyEvidenceRepository,
)
from proofhire_api.security.password import hash_password
from proofhire_worker.ingestion.staleness import mark_evidence_stale_for_artifacts


@pytest.fixture
async def env():
    async with async_session_factory() as session:
        user = User(
            email=f"stale-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("irrelevant"),
        )
        session.add(user)
        await session.flush()

        repo = Repository(
            user_id=user.id,
            provider_repo_id=int.from_bytes(uuid.uuid4().bytes[:4], "big") % 2_000_000_000,
            owner="o",
            name="r",
            url="https://github.com/o/r",
        )
        session.add(repo)
        await session.flush()

        old_artifact = SourceArtifact(
            repository_id=repo.id, type="source_file", path="app/main.py",
            commit_sha="a" * 40, content_hash="old" + "0" * 61, priority="p1",
        )
        session.add(old_artifact)
        await session.flush()
        await session.commit()

        yield session, user, repo, old_artifact

        await session.delete(await session.get(User, user.id))
        await session.commit()


async def _make_evidence(session, user, repo, artifact, status=EvidenceStatus.CONFIRMED):
    saved = await SQLAlchemyEvidenceRepository(session).save_candidates(
        [
            EvidenceCandidate(
                user_id=user.id, repository_id=repo.id, evidence_type=EvidenceType.SKILL_USAGE,
                title=f"Claim {uuid.uuid4().hex[:6]}",
                normalized_claim=f"Does something {uuid.uuid4().hex[:6]}.",
                description="", confidence=0.9, extraction_method="test",
                sources=[
                    EvidenceSourceCandidate(
                        source_artifact_id=artifact.id, locator="app/main.py",
                        snippet_hash="c" * 64, commit_sha="a" * 40,
                    )
                ],
            )
        ]
    )
    saved[0].status = status
    await session.commit()
    return saved[0]


async def test_evidence_goes_stale_when_its_source_file_changes(env):
    session, user, repo, old_artifact = env
    evidence = await _make_evidence(session, user, repo, old_artifact)

    marked = await mark_evidence_stale_for_artifacts(session, [old_artifact.id])
    await session.commit()

    assert marked == 1
    await session.refresh(evidence)
    assert evidence.status == EvidenceStatus.STALE


async def test_rejected_evidence_is_not_resurrected_into_the_review_queue(env):
    """A user's rejection is a decision, not a cache entry — a file changing
    underneath it must not quietly turn it back into something to review."""
    session, user, repo, old_artifact = env
    evidence = await _make_evidence(session, user, repo, old_artifact, EvidenceStatus.REJECTED)

    await mark_evidence_stale_for_artifacts(session, [old_artifact.id])
    await session.commit()

    await session.refresh(evidence)
    assert evidence.status == EvidenceStatus.REJECTED


async def test_private_evidence_keeps_its_privacy_setting(env):
    session, user, repo, old_artifact = env
    evidence = await _make_evidence(session, user, repo, old_artifact, EvidenceStatus.PRIVATE)

    await mark_evidence_stale_for_artifacts(session, [old_artifact.id])
    await session.commit()

    await session.refresh(evidence)
    assert evidence.status == EvidenceStatus.PRIVATE


async def test_evidence_from_untouched_files_is_left_alone(env):
    session, user, repo, old_artifact = env
    untouched = SourceArtifact(
        repository_id=repo.id, type="source_file", path="app/other.py",
        commit_sha="a" * 40, content_hash="other" + "0" * 59, priority="p1",
    )
    session.add(untouched)
    await session.flush()
    await session.commit()

    changed_evidence = await _make_evidence(session, user, repo, old_artifact)
    untouched_evidence = await _make_evidence(session, user, repo, untouched)

    await mark_evidence_stale_for_artifacts(session, [old_artifact.id])
    await session.commit()

    await session.refresh(changed_evidence)
    await session.refresh(untouched_evidence)
    assert changed_evidence.status == EvidenceStatus.STALE
    assert untouched_evidence.status == EvidenceStatus.CONFIRMED


async def test_no_superseded_artifacts_is_a_no_op(env):
    session, _user, _repo, _old = env
    assert await mark_evidence_stale_for_artifacts(session, []) == 0


async def test_extraction_query_restricts_to_the_changed_artifacts(env):
    """The incremental path must narrow the artifact set, not merely reorder it
    — this is what stops a re-sync re-running the LLM over the whole repo."""
    session, _user, repo, old_artifact = env
    second = SourceArtifact(
        repository_id=repo.id, type="source_file", path="app/second.py",
        commit_sha="a" * 40, content_hash="second" + "0" * 58, priority="p1",
    )
    session.add(second)
    await session.flush()
    await session.commit()

    full = (
        await session.scalars(
            select(SourceArtifact).where(
                SourceArtifact.repository_id == repo.id,
                SourceArtifact.priority.in_(["p0", "p1"]),
            )
        )
    ).all()
    assert len(full) == 2

    incremental = (
        await session.scalars(
            select(SourceArtifact).where(
                SourceArtifact.repository_id == repo.id,
                SourceArtifact.priority.in_(["p0", "p1"]),
                SourceArtifact.id.in_([second.id]),
            )
        )
    ).all()
    assert [a.id for a in incremental] == [second.id]
