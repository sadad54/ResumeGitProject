"""EvidenceRepository: the boundary worker/intelligence code depends on instead of
importing SQLAlchemy directly (PRD §35). The worker submits typed DTOs
(EvidenceCandidate) and reads back typed results (EvidenceHit) — it never sees an
ORM model or writes a query.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.models.evidence import Evidence, EvidenceSkill, EvidenceSource
from proofhire_api.models.skill import Skill
from proofhire_contracts import EvidenceStatus, EvidenceType


@dataclass
class EvidenceSourceCandidate:
    source_artifact_id: uuid.UUID
    locator: str
    snippet_hash: str
    commit_sha: str
    line_start: int | None = None
    line_end: int | None = None
    relevance: float = 1.0


@dataclass
class EvidenceCandidate:
    user_id: uuid.UUID
    repository_id: uuid.UUID
    evidence_type: EvidenceType
    title: str
    normalized_claim: str
    description: str
    confidence: float
    extraction_method: str
    sources: list[EvidenceSourceCandidate]
    skill_names: list[str] = field(default_factory=list)
    embedding: list[float] | None = None


@dataclass
class EvidenceHit:
    id: uuid.UUID
    title: str
    normalized_claim: str
    evidence_type: EvidenceType
    confidence: float
    score: float


@dataclass
class EvidenceQuery:
    user_id: uuid.UUID
    text: str
    embedding: list[float] | None = None
    limit: int = 10


class EvidenceRepository(Protocol):
    async def save_candidates(self, items: list[EvidenceCandidate]) -> list[Evidence]: ...

    async def hybrid_search(self, query: EvidenceQuery) -> list[EvidenceHit]: ...


class SQLAlchemyEvidenceRepository:
    """Concrete implementation. Only this module and its tests should import
    SQLAlchemy models for Evidence — everything else goes through the Protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _resolve_skill(self, name: str) -> Skill:
        normalized = name.strip().lower()
        existing = await self._session.scalar(select(Skill).where(Skill.canonical_name == normalized))
        if existing is not None:
            return existing
        skill = Skill(canonical_name=normalized, aliases=[name] if name != normalized else [])
        self._session.add(skill)
        await self._session.flush()
        return skill

    async def save_candidates(self, items: list[EvidenceCandidate]) -> list[Evidence]:
        saved: list[Evidence] = []

        for item in items:
            if not item.sources:
                # PRD §14: every Evidence node MUST have at least one EvidenceSource.
                # Silently dropping instead of raising keeps one bad candidate from
                # failing an entire extraction batch — the caller logs the count.
                continue

            duplicate = await self._session.scalar(
                select(Evidence).where(
                    Evidence.repository_id == item.repository_id,
                    Evidence.normalized_claim == item.normalized_claim,
                    Evidence.status.in_([EvidenceStatus.CONFIRMED, EvidenceStatus.CANDIDATE]),
                )
            )
            if duplicate is not None:
                continue

            evidence = Evidence(
                user_id=item.user_id,
                repository_id=item.repository_id,
                evidence_type=item.evidence_type,
                title=item.title,
                normalized_claim=item.normalized_claim,
                description=item.description,
                confidence=item.confidence,
                extraction_method=item.extraction_method,
                status=EvidenceStatus.CANDIDATE,
                embedding=item.embedding,
            )
            self._session.add(evidence)
            await self._session.flush()  # assigns evidence.id

            for source in item.sources:
                self._session.add(
                    EvidenceSource(
                        evidence_id=evidence.id,
                        source_artifact_id=source.source_artifact_id,
                        locator=source.locator,
                        snippet_hash=source.snippet_hash,
                        line_start=source.line_start,
                        line_end=source.line_end,
                        commit_sha=source.commit_sha,
                        relevance=source.relevance,
                    )
                )

            for skill_name in item.skill_names:
                skill = await self._resolve_skill(skill_name)
                self._session.add(EvidenceSkill(evidence_id=evidence.id, skill_id=skill.id, strength=1.0))

            saved.append(evidence)

        await self._session.commit()
        return saved

    async def hybrid_search(self, query: EvidenceQuery) -> list[EvidenceHit]:
        """Minimal Phase-2 implementation: lexical substring match only. Full
        hybrid (lexical + vector + entity overlap) fusion + reranking lands in
        Phase 4 per the build plan's spike on fusion strategy (ADR-0006)."""
        stmt = (
            select(Evidence)
            .where(
                Evidence.user_id == query.user_id,
                Evidence.status != EvidenceStatus.REJECTED,
                Evidence.normalized_claim.ilike(f"%{query.text}%"),
            )
            .limit(query.limit)
        )
        results = await self._session.scalars(stmt)
        return [
            EvidenceHit(
                id=e.id,
                title=e.title,
                normalized_claim=e.normalized_claim,
                evidence_type=e.evidence_type,
                confidence=e.confidence,
                score=1.0,
            )
            for e in results.all()
        ]
