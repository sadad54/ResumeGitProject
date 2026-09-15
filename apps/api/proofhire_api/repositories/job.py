"""JobRepository: the boundary worker/intelligence's JD-analysis task depends on
instead of importing SQLAlchemy directly (PRD §35 applies this pattern beyond
just Evidence)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.models.job import Job
from proofhire_api.models.requirement import Requirement
from proofhire_contracts import RequirementCategory


@dataclass
class RequirementCandidate:
    category: RequirementCategory
    text: str
    normalized: list[str]
    importance: float
    required: bool
    confidence: float = 1.0


@dataclass
class JobAnalysisResult:
    role: str | None
    company: str | None
    seniority: str | None
    requirements: list[RequirementCandidate] = field(default_factory=list)


class JobRepository(Protocol):
    async def save_analysis(self, job_id: uuid.UUID, result: JobAnalysisResult) -> list[Requirement]: ...


class SQLAlchemyJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_analysis(self, job_id: uuid.UUID, result: JobAnalysisResult) -> list[Requirement]:
        job = await self._session.get(Job, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        # JD-stated role/company/seniority take priority; only fill in what the
        # user's source text didn't already establish via prior manual entry.
        if result.role and not job.role:
            job.role = result.role
        if result.company and not job.company:
            job.company = result.company
        if result.seniority and not job.seniority:
            job.seniority = result.seniority
        job.status = "analyzed"

        # Re-analysis dedup: skip requirements whose exact text already exists
        # for this job, rather than accumulating duplicate rows on re-runs.
        existing_texts = set(
            await self._session.scalars(
                select(Requirement.text).where(Requirement.job_id == job_id)
            )
        )

        saved: list[Requirement] = []
        for candidate in result.requirements:
            if candidate.text in existing_texts:
                continue
            requirement = Requirement(
                job_id=job_id,
                category=candidate.category,
                text=candidate.text,
                normalized=candidate.normalized,
                importance=candidate.importance,
                required=candidate.required,
                confidence=candidate.confidence,
            )
            self._session.add(requirement)
            saved.append(requirement)
            existing_texts.add(candidate.text)

        await self._session.commit()
        return saved
