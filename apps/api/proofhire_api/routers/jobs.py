import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import get_db
from proofhire_api.dependencies import get_current_user
from proofhire_api.models.job import Job
from proofhire_api.models.requirement import Requirement
from proofhire_api.models.user import User
from proofhire_api.schemas.job import AnalyzeResponse, JobCreateRequest, JobPublic, RequirementPublic
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
