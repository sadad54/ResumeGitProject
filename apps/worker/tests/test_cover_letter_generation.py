"""Mirrors test_generation_pipeline.py's safety proof, for the cover letter
path: a paragraph asserting an invented metric must be stripped even when the
mock LLM claim verifier says it's supported.
"""

import re
import uuid

import pytest
from proofhire_contracts import (
    ClaimVerificationStatus,
    EvidenceType,
    ProfileFactType,
    RequirementCategory,
    TailoringMode,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import async_session_factory
from proofhire_api.models.evidence_match import EvidenceMatch
from proofhire_api.models.generated_claim import GeneratedClaim
from proofhire_api.models.generated_document import GeneratedDocument
from proofhire_api.models.job import Job
from proofhire_api.models.profile_fact import ProfileFact
from proofhire_api.models.repository import Repository
from proofhire_api.models.requirement import Requirement
from proofhire_api.models.source_artifact import SourceArtifact
from proofhire_api.models.user import User
from proofhire_api.repositories.evidence import (
    EvidenceCandidate,
    EvidenceSourceCandidate,
    SQLAlchemyEvidenceRepository,
)
from proofhire_api.security.password import hash_password
from proofhire_worker.intelligence.providers.mock_provider import MockLLMProvider
from proofhire_worker.intelligence.schemas import ClaimOutput, CoverLetterContentOutput, PositioningOutput

REAL_METRIC = "40%"
INVENTED_METRIC = "500%"


@pytest.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def fixture_env(db_session: AsyncSession):
    user = User(
        email=f"coverletter-test-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("irrelevant"),
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        ProfileFact(
            user_id=user.id, type=ProfileFactType.EMPLOYMENT,
            value_json={"employer": "Acme", "title": "SWE", "start_date": "2019", "end_date": "2021"},
            source="resume_upload", immutable=True, confirmed=True,
        )
    )

    repo = Repository(
        user_id=user.id,
        provider_repo_id=int.from_bytes(uuid.uuid4().bytes[:4], "big") % 2_000_000_000,
        owner="testowner", name="testrepo", url="https://github.com/testowner/testrepo",
    )
    db_session.add(repo)
    await db_session.flush()

    artifact = SourceArtifact(
        repository_id=repo.id, type="source_file", path="app/optimize.py",
        commit_sha="a" * 40, content_hash="b" * 64, priority="p1",
    )
    db_session.add(artifact)
    await db_session.flush()

    evidence_repo = SQLAlchemyEvidenceRepository(db_session)
    [evidence] = await evidence_repo.save_candidates(
        [
            EvidenceCandidate(
                user_id=user.id, repository_id=repo.id, evidence_type=EvidenceType.PERFORMANCE_METRIC,
                title="Query optimization",
                normalized_claim=f"Reduced query latency by {REAL_METRIC}.",
                description=f"Rewrote the query planner, reducing latency by {REAL_METRIC}.",
                confidence=0.9, extraction_method="test",
                sources=[EvidenceSourceCandidate(
                    source_artifact_id=artifact.id, locator="app/optimize.py",
                    snippet_hash="c" * 64, commit_sha="a" * 40,
                )],
            )
        ]
    )

    job = Job(user_id=user.id, source_text="fixture JD", role="Backend Engineer")
    db_session.add(job)
    await db_session.flush()

    requirement = Requirement(
        job_id=job.id, category=RequirementCategory.SKILL, text="Database performance experience",
        normalized=["performance"], importance=0.8, required=True,
    )
    db_session.add(requirement)
    await db_session.flush()

    db_session.add(
        EvidenceMatch(
            requirement_id=requirement.id, evidence_id=evidence.id,
            retrieval_score=0.9, rerank_score=0.9,
            match_reason="Directly demonstrates DB performance work.", status="strong",
        )
    )
    await db_session.commit()

    yield user, job, evidence

    async with async_session_factory() as cleanup_session:
        await cleanup_session.delete(await cleanup_session.get(User, user.id))
        await cleanup_session.commit()


def _position_fixture(task, messages, schema):
    return schema(
        target_identity="Backend engineer focused on database performance.",
        themes=["Database performance"], project_priority=["Query optimization"],
        skills_priority=["sql"], gaps_to_avoid=[],
    )


def _cover_letter_write_fixture(task, messages, schema):
    return schema(
        body_paragraphs=[
            "I'm excited to apply for this backend role.",
            f"In my previous work, I reduced query latency by {REAL_METRIC} through query planner improvements.",
            f"I also once reduced latency by {INVENTED_METRIC}, an achievement never actually recorded anywhere.",
            "I'd welcome the chance to bring this focus on measurable performance to your team.",
        ]
    )


def _make_claim_verify_fixture(evidence_id: str):
    def _fixture(task, messages, schema):
        user_content = messages[-1].content
        lines = re.findall(r"\[(\d+)\] (.+)", user_content)
        claims = []
        for idx_str, text in lines:
            idx = int(idx_str)
            if REAL_METRIC in text:
                claims.append(ClaimOutput(
                    bullet_index=idx, claim_text=text, claim_type="metric",
                    asserted_value=REAL_METRIC, referenced_evidence_id=evidence_id,
                    status="supported", reason="Matches evidence.",
                ))
            elif INVENTED_METRIC in text:
                claims.append(ClaimOutput(
                    bullet_index=idx, claim_text=text, claim_type="metric",
                    asserted_value=INVENTED_METRIC, referenced_evidence_id=evidence_id,
                    status="supported", reason="Sounds plausible.",  # LLM fooled, guard must override
                ))
            else:
                claims.append(ClaimOutput(
                    bullet_index=idx, claim_text=text, claim_type="other",
                    status="supported", reason="Generic framing, no specific factual claim.",
                ))
        return schema(claims=claims)

    return _fixture


@pytest.mark.asyncio
async def test_cover_letter_strips_invented_metric_despite_llm_approval(db_session, fixture_env, monkeypatch):
    user, job, evidence = fixture_env

    provider = MockLLMProvider(
        fixtures={
            "position": _position_fixture,
            "cover_letter_write": _cover_letter_write_fixture,
            "claim_verify": _make_claim_verify_fixture(str(evidence.id)),
        }
    )

    import proofhire_worker.intelligence.generation as generation_module
    import proofhire_worker.intelligence.positioning as positioning_module

    monkeypatch.setattr(generation_module, "get_provider", lambda: provider)
    monkeypatch.setattr(positioning_module, "get_provider", lambda: provider)

    await generation_module._generate(str(job.id), TailoringMode.CONSERVATIVE.value, "cover_letter")

    document = await db_session.scalar(
        select(GeneratedDocument).where(GeneratedDocument.job_id == job.id)
    )
    assert document is not None

    paragraphs = document.content_json["body_paragraphs"]
    assert any(REAL_METRIC in p for p in paragraphs)
    assert not any(INVENTED_METRIC in p for p in paragraphs)

    claims = list(
        await db_session.scalars(select(GeneratedClaim).where(GeneratedClaim.document_id == document.id))
    )
    invented = [c for c in claims if INVENTED_METRIC in c.claim_text]
    assert invented and all(c.verification_status == ClaimVerificationStatus.UNSUPPORTED for c in invented)
