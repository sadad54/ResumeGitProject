"""End-to-end integration test against the real DB for the generation
pipeline's core safety promise (PRD §37 item 13): a deliberately-planted
unsupported claim must be caught and stripped, even when the LLM claim
verifier itself (deliberately, in this test's fixture) says it's fine — this
is exactly the scenario the deterministic fact guard exists to catch.

Uses a MockLLMProvider with fixtures registered per task, monkeypatched in
place of the real provider so this runs with zero API cost/network calls.
"""

import re
import uuid

import pytest
from proofhire_contracts import ClaimVerificationStatus, EvidenceType, ProfileFactType, TailoringMode
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
from proofhire_contracts import RequirementCategory
from proofhire_worker.intelligence.providers.mock_provider import MockLLMProvider
from proofhire_worker.intelligence.schemas import (
    ClaimOutput,
    ClaimVerificationOutput,
    ExperienceEntryOutput,
    PositioningOutput,
    ResumeContentOutput,
)

REAL_METRIC = "30%"
INVENTED_METRIC = "999%"


@pytest.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def fixture_env(db_session: AsyncSession):
    user = User(
        email=f"generation-test-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("irrelevant"),
    )
    db_session.add(user)
    await db_session.flush()

    profile_fact = ProfileFact(
        user_id=user.id,
        type=ProfileFactType.EMPLOYMENT,
        value_json={"employer": "Google", "title": "SWE", "start_date": "2020", "end_date": "2022"},
        source="resume_upload",
        immutable=True,
        confirmed=True,
    )
    db_session.add(profile_fact)

    repo = Repository(
        user_id=user.id,
        provider_repo_id=int.from_bytes(uuid.uuid4().bytes[:4], "big") % 2_000_000_000,
        owner="testowner", name="testrepo", url="https://github.com/testowner/testrepo",
    )
    db_session.add(repo)
    await db_session.flush()

    artifact = SourceArtifact(
        repository_id=repo.id, type="source_file", path="app/cache.py",
        commit_sha="a" * 40, content_hash="b" * 64, priority="p1",
    )
    db_session.add(artifact)
    await db_session.flush()

    evidence_repo = SQLAlchemyEvidenceRepository(db_session)
    [evidence] = await evidence_repo.save_candidates(
        [
            EvidenceCandidate(
                user_id=user.id, repository_id=repo.id, evidence_type=EvidenceType.PERFORMANCE_METRIC,
                title="Caching optimization",
                normalized_claim=f"Improved throughput by {REAL_METRIC} via caching.",
                description=f"Added a caching layer that improved throughput by {REAL_METRIC}.",
                confidence=0.9, extraction_method="test",
                sources=[EvidenceSourceCandidate(
                    source_artifact_id=artifact.id, locator="app/cache.py",
                    snippet_hash="c" * 64, commit_sha="a" * 40,
                )],
            )
        ]
    )

    job = Job(user_id=user.id, source_text="fixture JD", role="Backend Engineer")
    db_session.add(job)
    await db_session.flush()

    requirement = Requirement(
        job_id=job.id, category=RequirementCategory.SKILL, text="Performance optimization experience",
        normalized=["performance"], importance=0.8, required=True,
    )
    db_session.add(requirement)
    await db_session.flush()

    db_session.add(
        EvidenceMatch(
            requirement_id=requirement.id, evidence_id=evidence.id,
            retrieval_score=0.9, rerank_score=0.9,
            match_reason="Directly demonstrates performance work.", status="strong",
        )
    )
    await db_session.commit()

    yield user, job, evidence

    async with async_session_factory() as cleanup_session:
        await cleanup_session.delete(await cleanup_session.get(User, user.id))
        await cleanup_session.commit()


def _position_fixture(task, messages, schema):
    return schema(
        target_identity="Backend engineer focused on performance.",
        themes=["Performance optimization"],
        project_priority=["Caching optimization"],
        skills_priority=["caching"],
        gaps_to_avoid=[],
    )


def _resume_write_fixture(task, messages, schema):
    return schema(
        summary="Backend engineer with a track record of measurable performance improvements.",
        skills=["Python", "Caching"],
        experience=[
            ExperienceEntryOutput(
                employer="Google", title="SWE", start_date="2020", end_date="2022",
                bullets=[
                    f"Improved throughput by {REAL_METRIC} via caching.",  # verbatim in evidence
                    f"Improved throughput by {INVENTED_METRIC} via magic.",  # never appears anywhere
                ],
            )
        ],
    )


def _make_claim_verify_fixture(evidence_id: str):
    def _fixture(task, messages, schema):
        user_content = messages[-1].content
        bullet_lines = re.findall(r"\[(\d+)\] (.+)", user_content)
        claims = []
        for idx_str, text in bullet_lines:
            idx = int(idx_str)
            if REAL_METRIC in text:
                claims.append(
                    ClaimOutput(
                        bullet_index=idx, claim_text=text, claim_type="metric",
                        asserted_value=REAL_METRIC, referenced_evidence_id=evidence_id,
                        status="supported", reason="Matches evidence exactly.",
                    )
                )
            elif INVENTED_METRIC in text:
                # The LLM itself is fooled here — it says "supported." This is
                # the exact scenario the deterministic guard must catch: an
                # overconfident LLM judgment must not be trusted for a metric
                # that doesn't actually appear in the cited evidence.
                claims.append(
                    ClaimOutput(
                        bullet_index=idx, claim_text=text, claim_type="metric",
                        asserted_value=INVENTED_METRIC, referenced_evidence_id=evidence_id,
                        status="supported", reason="Looks plausible.",
                    )
                )
            else:
                claims.append(
                    ClaimOutput(
                        bullet_index=idx, claim_text=text, claim_type="other",
                        status="supported", reason="General summary statement.",
                    )
                )
        return schema(claims=claims)

    return _fixture


@pytest.mark.asyncio
async def test_planted_unsupported_metric_is_caught_and_stripped(db_session, fixture_env, monkeypatch):
    user, job, evidence = fixture_env

    provider = MockLLMProvider(
        fixtures={
            "position": _position_fixture,
            "resume_write": _resume_write_fixture,
            "claim_verify": _make_claim_verify_fixture(str(evidence.id)),
        }
    )

    import proofhire_worker.intelligence.generation as generation_module
    import proofhire_worker.intelligence.positioning as positioning_module

    monkeypatch.setattr(generation_module, "get_provider", lambda: provider)
    monkeypatch.setattr(positioning_module, "get_provider", lambda: provider)

    await generation_module._generate(str(job.id), TailoringMode.CONSERVATIVE.value, "resume")

    document = await db_session.scalar(
        select(GeneratedDocument).where(GeneratedDocument.job_id == job.id)
    )
    assert document is not None

    all_bullets = [b for entry in document.content_json["experience"] for b in entry["bullets"]]
    assert any(REAL_METRIC in b for b in all_bullets), "verbatim-supported bullet should survive"
    assert not any(INVENTED_METRIC in b for b in all_bullets), (
        "invented metric must be stripped even though the mock LLM verifier said it was supported"
    )

    claims = list(
        await db_session.scalars(
            select(GeneratedClaim).where(GeneratedClaim.document_id == document.id)
        )
    )
    invented_claims = [c for c in claims if INVENTED_METRIC in c.claim_text]
    assert invented_claims, "the invented claim should still be recorded, just marked unsupported"
    assert all(c.verification_status == ClaimVerificationStatus.UNSUPPORTED for c in invented_claims)

    real_claims = [c for c in claims if REAL_METRIC in c.claim_text]
    assert all(c.verification_status == ClaimVerificationStatus.SUPPORTED for c in real_claims)
