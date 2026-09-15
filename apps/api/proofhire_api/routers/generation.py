import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import get_db
from proofhire_api.dependencies import get_current_user
from proofhire_api.models.evidence import Evidence, EvidenceSource
from proofhire_api.models.generated_claim import ClaimEvidence, GeneratedClaim
from proofhire_api.models.generated_document import GeneratedDocument
from proofhire_api.models.generation_run import GenerationRun
from proofhire_api.models.job import Job
from proofhire_api.models.repository import Repository
from proofhire_api.models.user import User
from proofhire_api.schemas.generation import (
    GenerateRequest,
    GenerateResponse,
    GeneratedClaimPublic,
    GeneratedDocumentPublic,
    GenerationRunPublic,
    PositioningResponse,
)

router = APIRouter(prefix="/api/v1", tags=["generation"])


@router.post("/jobs/{job_id}/positioning", response_model=PositioningResponse)
async def get_positioning(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PositioningResponse:
    """Synchronous (not queued): one bounded LLM call, same rationale as resume
    upload. Not persisted — this is an ephemeral preview the user reviews
    before generating; POST /jobs/{id}/generate recomputes it internally as
    part of the same pipeline run, so nothing is lost by not storing it here."""
    job = await db.get(Job, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    from proofhire_worker.intelligence.positioning import compute_positioning

    output, _result = await compute_positioning(db, job)
    return PositioningResponse(**output.model_dump())


@router.post("/jobs/{job_id}/generate", response_model=GenerateResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_generate(
    job_id: uuid.UUID,
    body: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    job = await db.get(Job, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    from proofhire_worker.broker import broker  # noqa: F401  (configures the Redis broker)
    from proofhire_worker.intelligence.generation import generate_document

    generate_document.send(str(job.id), body.mode.value, body.document_type.value)

    return GenerateResponse(status="queued")


@router.get("/generation-runs/{run_id}", response_model=GenerationRunPublic)
async def get_generation_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationRun:
    run = await db.get(GenerationRun, run_id)
    if run is None or run.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Generation run not found")
    return run


@router.get("/documents/{document_id}", response_model=GeneratedDocumentPublic)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GeneratedDocument:
    document = await db.get(GeneratedDocument, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    job = await db.get(Job, document.job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document


@router.get("/documents/{document_id}/claims", response_model=list[GeneratedClaimPublic])
async def get_document_claims(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GeneratedClaimPublic]:
    """Backs the resume workspace's provenance rail (PRD §11.4): click a
    bullet, see exactly which repository/file it traces back to."""
    document = await db.get(GeneratedDocument, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    job = await db.get(Job, document.job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    claims = list(
        await db.scalars(select(GeneratedClaim).where(GeneratedClaim.document_id == document_id))
    )

    results: list[GeneratedClaimPublic] = []
    for claim in claims:
        claim_evidence = await db.scalar(
            select(ClaimEvidence).where(ClaimEvidence.claim_id == claim.id)
        )
        evidence = None
        repository = None
        source_locator = None
        if claim_evidence is not None:
            evidence = await db.get(Evidence, claim_evidence.evidence_id)
            if evidence is not None:
                repository = await db.get(Repository, evidence.repository_id)
                source = await db.scalar(
                    select(EvidenceSource).where(EvidenceSource.evidence_id == evidence.id)
                )
                source_locator = source.locator if source else None

        results.append(
            GeneratedClaimPublic(
                id=claim.id,
                claim_text=claim.claim_text,
                claim_type=claim.claim_type,
                verification_status=claim.verification_status,
                confidence=claim.confidence,
                evidence_id=evidence.id if evidence else None,
                evidence_title=evidence.title if evidence else None,
                evidence_repository=f"{repository.owner}/{repository.name}" if repository else None,
                source_locator=source_locator,
            )
        )

    return results
