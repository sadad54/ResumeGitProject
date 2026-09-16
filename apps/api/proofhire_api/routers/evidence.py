import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import get_db
from proofhire_api.dependencies import get_current_user
from proofhire_api.models.evidence import Evidence, EvidenceSkill, EvidenceSource
from proofhire_api.models.skill import Skill
from proofhire_api.models.user import User
from proofhire_api.repositories.evidence import EvidenceQuery, SQLAlchemyEvidenceRepository
from proofhire_api.schemas.evidence import (
    EvidenceDetail,
    EvidencePatch,
    EvidencePublic,
    EvidenceSearchHit,
    EvidenceSearchRequest,
    EvidenceSourcePublic,
)
from proofhire_api.schemas.graph import EvidenceGraph
from proofhire_api.services.evidence_graph import project_graph

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])


@router.get("/graph", response_model=EvidenceGraph)
async def get_evidence_graph(
    job_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceGraph:
    return await project_graph(db, current_user.id, job_id, repository_id, limit)


@router.get("", response_model=list[EvidencePublic])
async def list_evidence(
    repository_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Evidence]:
    stmt = select(Evidence).where(Evidence.user_id == current_user.id)
    if repository_id is not None:
        stmt = stmt.where(Evidence.repository_id == repository_id)
    stmt = stmt.order_by(Evidence.created_at.desc())
    result = await db.scalars(stmt)
    return list(result.all())


@router.get("/{evidence_id}", response_model=EvidenceDetail)
async def get_evidence(
    evidence_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceDetail:
    evidence = await db.get(Evidence, evidence_id)
    if evidence is None or evidence.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")

    sources = await db.scalars(
        select(EvidenceSource).where(EvidenceSource.evidence_id == evidence_id)
    )
    skill_names = await db.scalars(
        select(Skill.canonical_name)
        .join(EvidenceSkill, EvidenceSkill.skill_id == Skill.id)
        .where(EvidenceSkill.evidence_id == evidence_id)
    )

    return EvidenceDetail(
        **EvidencePublic.model_validate(evidence).model_dump(),
        sources=[EvidenceSourcePublic.model_validate(s) for s in sources.all()],
        skills=list(skill_names.all()),
    )


@router.patch("/{evidence_id}", response_model=EvidencePublic)
async def patch_evidence(
    evidence_id: uuid.UUID,
    body: EvidencePatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Evidence:
    """Approve/reject/mark-private (PRD §9.1 Evidence Review). Only status is
    user-editable in V1 — editing claim text is deferred; a user who disagrees
    with a claim rejects it rather than rewriting AI-generated text, which would
    reintroduce the provenance problem ProofHire exists to solve."""
    evidence = await db.get(Evidence, evidence_id)
    if evidence is None or evidence.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    evidence.status = body.status
    await db.commit()
    await db.refresh(evidence)
    return evidence


@router.post("/search", response_model=list[EvidenceSearchHit])
async def search_evidence(
    body: EvidenceSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EvidenceSearchHit]:
    repo = SQLAlchemyEvidenceRepository(db)
    hits = await repo.hybrid_search(
        EvidenceQuery(user_id=current_user.id, text=body.text, limit=body.limit)
    )
    return [EvidenceSearchHit(**h.__dict__) for h in hits]
