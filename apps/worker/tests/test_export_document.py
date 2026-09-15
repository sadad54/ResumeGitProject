"""Integration test against the real DB for the export pipeline: renders a
real PDF, validates parse-back, and persists storage refs. Also proves the
fail-closed behavior — a document whose SUPPORTED claim doesn't actually
appear in its own content_json (a corrupted/inconsistent record) must fail
export rather than silently produce an untrustworthy PDF.
"""

import uuid

import pytest
from proofhire_contracts import ClaimVerificationStatus, DocumentType, GenerationRunStatus
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import async_session_factory
from proofhire_api.models.generated_claim import GeneratedClaim
from proofhire_api.models.generated_document import GeneratedDocument
from proofhire_api.models.generation_run import GenerationRun
from proofhire_api.models.job import Job
from proofhire_api.models.user import User
from proofhire_api.security.password import hash_password
from proofhire_worker.render.export import ParseBackValidationError, export_document
from proofhire_worker.render.storage import read_bytes


@pytest.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def fixture_env(db_session: AsyncSession):
    user = User(
        email=f"export-test-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("irrelevant"),
    )
    db_session.add(user)
    await db_session.flush()

    job = Job(user_id=user.id, source_text="fixture JD")
    db_session.add(job)
    await db_session.flush()

    run = GenerationRun(user_id=user.id, job_id=job.id, pipeline_version="test", status=GenerationRunStatus.SUCCEEDED)
    db_session.add(run)
    await db_session.flush()
    await db_session.commit()

    yield user, job, run

    async with async_session_factory() as cleanup_session:
        await cleanup_session.delete(await cleanup_session.get(User, user.id))
        await cleanup_session.commit()


@pytest.mark.asyncio
async def test_export_renders_validates_and_stores_pdf(db_session, fixture_env):
    user, job, run = fixture_env
    content = {
        "summary": "Backend engineer with measurable performance improvements.",
        "skills": ["Python"],
        "experience": [
            {
                "employer": "Acme", "title": "SWE", "start_date": "2020", "end_date": "2022",
                "bullets": ["Improved throughput by 30% via caching."],
            }
        ],
    }
    document = GeneratedDocument(
        job_id=job.id, generation_run_id=run.id, type=DocumentType.RESUME,
        template_id="ats_minimal", content_json=content,
    )
    db_session.add(document)
    await db_session.flush()

    claim = GeneratedClaim(
        document_id=document.id, claim_text="Improved throughput by 30% via caching.",
        claim_type="metric", verification_status=ClaimVerificationStatus.SUPPORTED, confidence=1.0,
    )
    db_session.add(claim)
    await db_session.commit()

    result = await export_document(db_session, document, user.email)

    assert result.pdf_ref is not None
    assert result.html_ref is not None
    assert result.plaintext_ref is not None

    pdf_bytes = read_bytes(result.pdf_ref)
    assert pdf_bytes[:4] == b"%PDF"

    plaintext = read_bytes(result.plaintext_ref).decode("utf-8")
    assert "30%" in plaintext
    # The template CSS uppercases section headers (text-transform), so the
    # raw extracted text reads "SUMMARY" — case-insensitive check here,
    # matching how the actual parse-back validator normalizes both sides.
    assert "summary" in plaintext.lower()


@pytest.mark.asyncio
async def test_export_fails_closed_when_supported_claim_is_not_actually_in_content(db_session, fixture_env):
    """A corrupted/inconsistent record — a SUPPORTED claim referencing text
    that was never actually written into content_json — must not silently
    export a PDF that doesn't contain what its own claims table promises."""
    user, job, run = fixture_env
    content = {
        "summary": "Backend engineer.",
        "skills": [],
        "experience": [],
    }
    document = GeneratedDocument(
        job_id=job.id, generation_run_id=run.id, type=DocumentType.RESUME,
        template_id="ats_minimal", content_json=content,
    )
    db_session.add(document)
    await db_session.flush()

    db_session.add(
        GeneratedClaim(
            document_id=document.id,
            claim_text="This text was never actually rendered anywhere in the document.",
            claim_type="metric", verification_status=ClaimVerificationStatus.SUPPORTED, confidence=1.0,
        )
    )
    await db_session.commit()

    with pytest.raises(ParseBackValidationError) as exc_info:
        await export_document(db_session, document, user.email)

    assert "never actually rendered" in exc_info.value.missing[0]
