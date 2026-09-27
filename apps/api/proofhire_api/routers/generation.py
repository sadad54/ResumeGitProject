import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from proofhire_contracts import DocumentType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.config import get_settings
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
    DownloadLink,
    ExportResponse,
    GeneratedClaimPublic,
    GeneratedDocumentPublic,
    GenerateRequest,
    GenerateResponse,
    GenerationRunPublic,
    PositioningResponse,
)
from proofhire_api.security.rate_limit import export_rate_limit, generate_rate_limit
from proofhire_api.services.object_storage import get_object_storage

router = APIRouter(prefix="/api/v1", tags=["generation"])


async def _owned_document(
    document_id: uuid.UUID, current_user: User, db: AsyncSession
) -> GeneratedDocument:
    """404 (not 403) for someone else's document, so ids can't be probed."""
    document = await db.get(GeneratedDocument, document_id)
    if document is not None:
        job = await db.get(Job, document.job_id)
        if job is not None and job.user_id == current_user.id:
            return document
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")


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


@router.post(
    "/jobs/{job_id}/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(generate_rate_limit)],
)
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


@router.get("/documents", response_model=list[GeneratedDocumentPublic])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GeneratedDocument]:
    return list(
        await db.scalars(
            select(GeneratedDocument)
            .join(Job)
            .where(
                Job.user_id == current_user.id,
            )
            # Newest first. This used to order by the UUID primary key, which
            # is random, so the saved-documents list came back shuffled.
            .order_by(GeneratedDocument.created_at.desc(), GeneratedDocument.id)
            .limit(100)
        )
    )


@router.get("/documents/{document_id}", response_model=GeneratedDocumentPublic)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GeneratedDocument:
    return await _owned_document(document_id, current_user, db)


@router.post(
    "/documents/{document_id}/export",
    response_model=ExportResponse,
    dependencies=[Depends(export_rate_limit)],
)
async def export_document_endpoint(
    document_id: uuid.UUID,
    template: Literal["ats_minimal", "technical_dense", "modern_editorial"] | None = None,
    page_size: Literal["Letter", "A4"] = "Letter",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    """Synchronous (not queued): one bounded Playwright render + parse-back
    validation cycle, same rationale as resume upload and positioning."""
    document = await _owned_document(document_id, current_user, db)

    from proofhire_worker.render.export import ParseBackValidationError, export_document

    try:
        document = await export_document(
            db, document, current_user.email, template, page_size
        )
    except ParseBackValidationError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Export failed parse-back validation — missing content: {exc.missing}",
        ) from exc

    return ExportResponse(
        document_id=document.id,
        pdf_available=document.pdf_ref is not None,
        page_count=document.page_count,
        # A resume is expected to be one page; report overflow rather than
        # blocking it, since a longer document is sometimes what the user wants.
        overflowed=(document.type == DocumentType.RESUME and (document.page_count or 1) > 1),
    )


@router.get("/documents/{document_id}/download", response_model=DownloadLink)
async def get_download_link(
    document_id: uuid.UUID,
    format: Literal["pdf", "txt"] = "pdf",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DownloadLink:
    """Authorize here, then let the browser fetch the bytes straight from
    storage through a short-lived signed URL (checklist §17 "signed
    object-storage URLs"). The bytes never pass through this process, and the
    link carries no bearer token.

    410 when the export's files are gone — e.g. the single-container deploy
    restarted and its local disk was wiped. The stale refs are cleared so the
    document reads as not-yet-exported and the UI offers Export again, rather
    than every future download failing the same way.
    """
    document = await _owned_document(document_id, current_user, db)
    key = document.pdf_ref if format == "pdf" else document.plaintext_ref
    if key is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Not exported yet — export the document first"
        )

    storage = get_object_storage()
    if not await storage.exists(key):
        document.pdf_ref = document.html_ref = document.plaintext_ref = None
        document.exported_at = None
        await db.commit()
        raise HTTPException(status.HTTP_410_GONE, "This export has expired — export it again")

    kind = "resume" if document.type == DocumentType.RESUME else "cover-letter"
    filename = f"{kind}-v{document.version}-{str(document.id)[:8]}.{format}"
    link = storage.signed_url(
        key, filename=filename, ttl_seconds=get_settings().download_url_ttl_seconds
    )
    return DownloadLink(url=link.url, filename=filename, expires_at=link.expires_at)


@router.get("/documents/{document_id}/preview", response_class=HTMLResponse)
async def preview_document_html(
    document_id: uuid.UUID,
    template: Literal["ats_minimal", "technical_dense", "modern_editorial"] | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Live preview for the resume workspace (checklist §10.7).

    Runs the *same* template renderer the PDF export uses, minus the Chromium
    step, so what the user sees while switching templates is what the export
    will contain — not a separate React approximation that can drift from the
    real output. Nothing is persisted; this is read-only.
    """
    document = await _owned_document(document_id, current_user, db)

    from proofhire_worker.render.templates import render_cover_letter_html, render_resume_html

    if document.type == DocumentType.RESUME:
        html = render_resume_html(
            document.content_json, current_user.email, template or document.template_id
        )
    else:
        html = render_cover_letter_html(document.content_json, current_user.email)

    # The web app renders this inside a sandboxed iframe; the CSP here is
    # belt-and-braces so the document can't run script even if embedded
    # elsewhere. The renderer HTML-escapes all content, but generated text is
    # still model output and gets no more trust than it needs.
    return HTMLResponse(
        html,
        headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"},
    )


@router.get("/documents/{document_id}/claims", response_model=list[GeneratedClaimPublic])
async def get_document_claims(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GeneratedClaimPublic]:
    """Backs the resume workspace's provenance rail (PRD §11.4): click a
    bullet, see exactly which repository/file it traces back to.

    One query. It used to issue four per claim (link, evidence, repository,
    source), and took whichever link row came back first; this picks each
    claim's strongest supporting evidence and that evidence's most relevant
    source, deterministically.
    """
    await _owned_document(document_id, current_user, db)

    rows = await db.execute(
        select(
            GeneratedClaim,
            Evidence.id,
            Evidence.title,
            Repository.owner,
            Repository.name,
            EvidenceSource.locator,
        )
        .outerjoin(ClaimEvidence, ClaimEvidence.claim_id == GeneratedClaim.id)
        .outerjoin(Evidence, Evidence.id == ClaimEvidence.evidence_id)
        .outerjoin(Repository, Repository.id == Evidence.repository_id)
        .outerjoin(EvidenceSource, EvidenceSource.evidence_id == Evidence.id)
        .where(GeneratedClaim.document_id == document_id)
        .distinct(GeneratedClaim.id)
        .order_by(
            GeneratedClaim.id,
            ClaimEvidence.support_score.desc().nulls_last(),
            EvidenceSource.relevance.desc().nulls_last(),
        )
    )
    return [
        GeneratedClaimPublic(
            id=claim.id,
            claim_text=claim.claim_text,
            claim_type=claim.claim_type,
            verification_status=claim.verification_status,
            confidence=claim.confidence,
            evidence_id=evidence_id,
            evidence_title=evidence_title,
            evidence_repository=f"{owner}/{name}" if owner else None,
            source_locator=locator,
        )
        for claim, evidence_id, evidence_title, owner, name, locator in rows
    ]
