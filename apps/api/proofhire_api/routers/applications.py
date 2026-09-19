import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import get_db
from proofhire_api.dependencies import get_current_user
from proofhire_api.models.application import Application
from proofhire_api.models.job import Job
from proofhire_api.models.user import User
from proofhire_api.schemas.application import (
    ApplicationCreateRequest,
    ApplicationPatch,
    ApplicationPublic,
)

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


@router.post("", response_model=ApplicationPublic, status_code=status.HTTP_201_CREATED)
async def create_application(
    body: ApplicationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Application:
    job = await db.get(Job, body.job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    existing = await db.scalar(select(Application).where(Application.job_id == body.job_id))
    if existing is not None:
        return existing

    application = Application(user_id=current_user.id, job_id=body.job_id)
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return application


@router.get("", response_model=list[ApplicationPublic])
async def list_applications(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Application]:
    result = await db.scalars(
        select(Application)
        .where(Application.user_id == current_user.id)
        .order_by(Application.updated_at.desc(), Application.id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.all())


@router.patch("/{application_id}", response_model=ApplicationPublic)
async def patch_application(
    application_id: uuid.UUID,
    body: ApplicationPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Application:
    application = await db.get(Application, application_id)
    if application is None or application.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    application.stage = body.stage
    await db.commit()
    await db.refresh(application)
    return application
