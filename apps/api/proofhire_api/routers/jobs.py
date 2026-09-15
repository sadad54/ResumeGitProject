import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from proofhire_contracts import MatchLabel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import get_db
from proofhire_api.dependencies import get_current_user
from proofhire_api.models.evidence import Evidence
from proofhire_api.models.evidence_match import EvidenceMatch
from proofhire_api.models.job import Job
from proofhire_api.models.repository import Repository
from proofhire_api.models.requirement import Requirement
from proofhire_api.models.user import User
from proofhire_api.schemas.job import (
    AnalyzeResponse,
    CoverageRow,
    JobCreateRequest,
    JobPublic,
    RequirementPublic,
)
from proofhire_api.services.jd_fetch import JDFetchError, fetch_and_extract_text

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post("", response_model=JobPublic, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: JobCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Job:
    source_text = body.source_text
    if not source_text and body.source_url:
        try:
            source_text = await fetch_and_extract_text(body.source_url)
        except JDFetchError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    job = Job(user_id=current_user.id, source_url=body.source_url, source_text=source_text)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("", response_model=list[JobPublic])
async def list_jobs(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Job]:
    result = await db.scalars(
        select(Job).where(Job.user_id == current_user.id).order_by(Job.captured_at.desc())
    )
    return list(result.all())


@router.get("/{job_id}", response_model=JobPublic)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Job:
    job = await db.get(Job, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@router.post("/{job_id}/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_202_ACCEPTED)
async def analyze_job_endpoint(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyzeResponse:
    job = await db.get(Job, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    from proofhire_worker.broker import broker  # noqa: F401  (configures the Redis broker)
    from proofhire_worker.intelligence.job_analysis import analyze_job

    job.status = "analyzing"
    await db.commit()
    analyze_job.send(str(job.id))

    return AnalyzeResponse(job_id=job.id, status="queued")


@router.get("/{job_id}/requirements", response_model=list[RequirementPublic])
async def get_requirements(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Requirement]:
    job = await db.get(Job, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    result = await db.scalars(
        select(Requirement)
        .where(Requirement.job_id == job_id)
        .order_by(Requirement.importance.desc())
    )
    return list(result.all())


@router.get("/{job_id}/coverage", response_model=list[CoverageRow])
async def get_coverage(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CoverageRow]:
    """Evidence Coverage Matrix (PRD §18). A requirement with no EvidenceMatch
    row is an implicit Gap — the coverage engine never even retrieved a
    plausible candidate for it (PRD §17)."""
    job = await db.get(Job, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    requirements = list(
        await db.scalars(
            select(Requirement)
            .where(Requirement.job_id == job_id)
            .order_by(Requirement.importance.desc())
        )
    )

    rows: list[CoverageRow] = []
    for requirement in requirements:
        match = await db.scalar(
            select(EvidenceMatch).where(EvidenceMatch.requirement_id == requirement.id)
        )

        if match is None:
            rows.append(
                CoverageRow.build(
                    requirement_id=requirement.id,
                    requirement_text=requirement.text,
                    category=requirement.category,
                    required=requirement.required,
                    importance=requirement.importance,
                    match_label=MatchLabel.GAP,
                    evidence_id=None,
                    evidence_title=None,
                    evidence_repository=None,
                    confidence=None,
                    explanation="No candidate evidence was found for this requirement.",
                )
            )
            continue

        evidence = await db.get(Evidence, match.evidence_id)
        repository = await db.get(Repository, evidence.repository_id) if evidence else None

        rows.append(
            CoverageRow.build(
                requirement_id=requirement.id,
                requirement_text=requirement.text,
                category=requirement.category,
                required=requirement.required,
                importance=requirement.importance,
                match_label=match.status,
                evidence_id=evidence.id if evidence else None,
                evidence_title=evidence.title if evidence else None,
                evidence_repository=f"{repository.owner}/{repository.name}" if repository else None,
                confidence=evidence.confidence if evidence else None,
                explanation=match.match_reason,
            )
        )

    return rows
