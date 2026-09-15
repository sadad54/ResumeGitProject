"""EvidenceRepository: the boundary worker/intelligence code depends on instead of
importing SQLAlchemy directly (PRD §35). The worker submits typed DTOs
(EvidenceCandidate) and reads back typed results (EvidenceHit) — it never sees an
ORM model or writes a query.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.models.evidence import Evidence, EvidenceSkill, EvidenceSource
from proofhire_api.models.skill import Skill
from proofhire_contracts import EvidenceStatus, EvidenceType

# ADR-0006: weighted-sum fusion weights. Revisit once Phase 9's eval harness has
# real labeled data to tune against.
LEXICAL_WEIGHT = 0.35
VECTOR_WEIGHT = 0.45
SKILL_WEIGHT = 0.20


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
    lexical_score: float = 0.0
    vector_score: float = 0.0
    skill_score: float = 0.0


@dataclass
class EvidenceQuery:
    user_id: uuid.UUID
    text: str
    embedding: list[float] | None = None
    skill_keywords: list[str] = field(default_factory=list)
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
        """Weighted-sum fusion of lexical + vector + skill-overlap signals
        (ADR-0006). All three run in one SQL query against the GIN/IVFFlat
        indexes added in migration 0004."""
        has_embedding = query.embedding is not None
        has_keywords = bool(query.skill_keywords)

        vector_term = (
            "GREATEST(0, 1 - (e.embedding <=> CAST(:embedding AS vector)))"
            if has_embedding
            else "0"
        )
        skill_join = (
            """
            LEFT JOIN LATERAL (
                SELECT count(DISTINCT s.canonical_name)::float AS overlap_count
                FROM evidence_skills es
                JOIN skills s ON s.id = es.skill_id
                WHERE es.evidence_id = e.id AND s.canonical_name = ANY(:keywords)
            ) skill_overlap ON true
            """
            if has_keywords
            else ""
        )
        skill_term = (
            "LEAST(1.0, COALESCE(skill_overlap.overlap_count, 0) / :keyword_count)"
            if has_keywords
            else "0"
        )

        sql = f"""
            SELECT
                e.id, e.title, e.normalized_claim, e.evidence_type, e.confidence,
                LEAST(1.0, ts_rank_cd(e.search_vector, plainto_tsquery('english', :text))) AS lexical_score,
                {vector_term} AS vector_score,
                {skill_term} AS skill_score
            FROM evidence e
            {skill_join}
            WHERE e.user_id = :user_id AND e.status != 'rejected'
            ORDER BY (
                :lexical_weight * LEAST(1.0, ts_rank_cd(e.search_vector, plainto_tsquery('english', :text)))
                + :vector_weight * {vector_term}
                + :skill_weight * {skill_term}
            ) DESC
            LIMIT :limit
        """

        params: dict = {
            "user_id": str(query.user_id),
            "text": query.text,
            "lexical_weight": LEXICAL_WEIGHT,
            "vector_weight": VECTOR_WEIGHT,
            "skill_weight": SKILL_WEIGHT,
            "limit": query.limit,
        }
        if has_embedding:
            # pgvector's text input format is "[v1,v2,...]" with no spaces —
            # build it explicitly rather than relying on Python's list repr.
            params["embedding"] = "[" + ",".join(str(v) for v in query.embedding) + "]"
        if has_keywords:
            params["keywords"] = [k.strip().lower() for k in query.skill_keywords]
            params["keyword_count"] = float(len(query.skill_keywords))

        rows = (await self._session.execute(text(sql), params)).mappings().all()

        hits = []
        for row in rows:
            lexical = float(row["lexical_score"])
            vector = float(row["vector_score"])
            skill = float(row["skill_score"])
            score = LEXICAL_WEIGHT * lexical + VECTOR_WEIGHT * vector + SKILL_WEIGHT * skill
            if score <= 0:
                # No signal contributed at all — ORDER BY DESC guarantees these
                # are the lowest-ranked rows, so once we hit one we can stop.
                # Returning zero-relevance rows just to pad out to `limit` would
                # make completely unrelated evidence look like a retrieved
                # candidate to the reranker (PRD §17: Gap means no candidates,
                # not "whatever happened to be in the table").
                break
            hits.append(
                EvidenceHit(
                    id=row["id"],
                    title=row["title"],
                    normalized_claim=row["normalized_claim"],
                    evidence_type=EvidenceType(row["evidence_type"]),
                    confidence=float(row["confidence"]),
                    score=score,
                    lexical_score=lexical,
                    vector_score=vector,
                    skill_score=skill,
                )
            )
        return hits
