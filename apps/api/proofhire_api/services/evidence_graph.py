"""Bounded, tenant-scoped projection over existing domain rows (ADR-0014)."""

import uuid
from collections import defaultdict
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.models.evidence import Evidence, EvidenceSkill, EvidenceSource
from proofhire_api.models.evidence_match import EvidenceMatch
from proofhire_api.models.job import Job
from proofhire_api.models.repository import Repository
from proofhire_api.models.requirement import Requirement
from proofhire_api.models.skill import Skill
from proofhire_api.models.source_artifact import SourceArtifact
from proofhire_api.schemas.graph import EvidenceGraph, GraphEdge, GraphNode, GraphSource


def weight(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


async def project_graph(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID | None,
    repository_id: uuid.UUID | None,
    limit: int,
) -> EvidenceGraph:
    job = None
    if job_id:
        job = await db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))
        if job is None:
            raise HTTPException(404, "Job not found")
    if repository_id:
        owned = await db.scalar(
            select(Repository.id).where(
                Repository.id == repository_id,
                Repository.user_id == user_id,
            )
        )
        if owned is None:
            raise HTTPException(404, "Repository not found")

    stmt = (
        select(Evidence, Repository)
        .join(Repository)
        .where(
            Evidence.user_id == user_id,
            Repository.user_id == user_id,
            Evidence.status.in_(["candidate", "confirmed"]),
            Evidence.superseded_by.is_(None),
        )
        .order_by(Evidence.created_at.desc(), Evidence.id)
    )
    if repository_id:
        stmt = stmt.where(Evidence.repository_id == repository_id)
    rows = list((await db.execute(stmt.limit(limit + 1))).all())
    truncated = len(rows) > limit
    rows = rows[:limit]
    evidence_ids = [e.id for e, _ in rows]
    repos = {e.id: r for e, r in rows}
    sources: dict = defaultdict(list)
    if evidence_ids:
        # Reject malformed cross-repository provenance as well as cross-user joins.
        source_rows = (
            await db.execute(
                select(EvidenceSource, SourceArtifact)
                .join(
                    SourceArtifact,
                    SourceArtifact.id == EvidenceSource.source_artifact_id,
                )
                .join(Evidence, Evidence.id == EvidenceSource.evidence_id)
                .where(
                    EvidenceSource.evidence_id.in_(evidence_ids),
                    SourceArtifact.repository_id == Evidence.repository_id,
                )
                .order_by(EvidenceSource.locator, EvidenceSource.id)
            )
        ).all()
        for source, artifact in source_rows:
            repo = repos[source.evidence_id]
            url = (
                f"https://github.com/{quote(repo.owner, safe='')}/{quote(repo.name, safe='')}"
                f"/blob/{quote(source.commit_sha, safe='')}/{quote(artifact.path, safe='/')}"
            )
            if source.line_start:
                url += f"#L{source.line_start}"
                if source.line_end:
                    url += f"-L{source.line_end}"
            sources[source.evidence_id].append(
                GraphSource(
                    locator=source.locator,
                    url=url,
                    commit_sha=source.commit_sha,
                    line_start=source.line_start,
                    line_end=source.line_end,
                )
            )

    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    visible_ids = set()
    for evidence, repo in rows:
        # Current Evidence schema is repository-backed: orphan rows are not proof.
        if not sources[evidence.id]:
            continue
        visible_ids.add(evidence.id)
        project_key, evidence_key = f"project:{repo.id}", f"evidence:{evidence.id}"
        nodes[project_key] = GraphNode(
            id=project_key,
            kind="project",
            label=f"{repo.owner}/{repo.name}",
            repository_id=str(repo.id),
            description="Repository source",
        )
        nodes[evidence_key] = GraphNode(
            id=evidence_key,
            kind="architecture" if evidence.evidence_type == "architecture" else "evidence",
            label=evidence.title,
            description=evidence.normalized_claim,
            status=evidence.status,
            confidence=weight(evidence.confidence),
            repository_id=str(repo.id),
            evidence_id=str(evidence.id),
            sources=sources[evidence.id],
        )
        edges.append(
            GraphEdge(
                id=f"contains:{evidence.id}",
                source=project_key,
                target=evidence_key,
                kind="contains",
                weight=weight(evidence.confidence),
            )
        )
    if visible_ids:
        skill_rows = (
            await db.execute(
                select(EvidenceSkill, Skill)
                .join(Skill)
                .where(
                    EvidenceSkill.evidence_id.in_(visible_ids),
                )
                .order_by(Skill.canonical_name, EvidenceSkill.evidence_id)
            )
        ).all()
        for link, skill in skill_rows:
            key = f"skill:{skill.id}"
            nodes[key] = GraphNode(id=key, kind="skill", label=skill.canonical_name)
            edges.append(
                GraphEdge(
                    id=f"skill:{link.evidence_id}:{skill.id}",
                    source=f"evidence:{link.evidence_id}",
                    target=key,
                    kind="demonstrates",
                    weight=weight(link.strength),
                )
            )

    if job:
        requirements = list(
            await db.scalars(
                select(Requirement)
                .where(
                    Requirement.job_id == job.id,
                )
                .order_by(Requirement.importance.desc(), Requirement.id)
                .limit(501)
            )
        )
        truncated = truncated or len(requirements) > 500
        requirements = requirements[:500]
        existing_match_ids = (
            set(
                await db.scalars(
                    select(EvidenceMatch.requirement_id).where(
                        EvidenceMatch.requirement_id.in_([r.id for r in requirements]),
                    )
                )
            )
            if requirements
            else set()
        )
        matches: dict = defaultdict(list)
        if requirements and visible_ids and job.status not in {"analyzing", "matching", "failed"}:
            match_rows = await db.scalars(
                select(EvidenceMatch)
                .join(
                    Evidence,
                    Evidence.id == EvidenceMatch.evidence_id,
                )
                .where(
                    EvidenceMatch.requirement_id.in_([r.id for r in requirements]),
                    EvidenceMatch.evidence_id.in_(visible_ids),
                    Evidence.user_id == user_id,
                    Evidence.status == "confirmed",
                )
                .order_by(EvidenceMatch.id)
            )
            for match in match_rows:
                matches[match.requirement_id].append(match)
        rank = {"strong": 3, "partial": 2, "unknown": 1, "gap": 0}
        for requirement in requirements:
            key = f"requirement:{requirement.id}"
            related = matches[requirement.id]
            # Absence is not proof of a gap: may be pending, failed, filtered,
            # truncated, or a formerly visible match. Preserve uncertainty.
            label = max((m.status for m in related), key=lambda s: rank[s], default="unknown")
            if not related and job.status == "ready" and requirement.id not in existing_match_ids:
                label = "gap"
            nodes[key] = GraphNode(
                id=key,
                kind="requirement",
                label=requirement.text,
                description=("Required" if requirement.required else "Preferred")
                + f" · {requirement.category}",
                status=label,
                required=requirement.required,
            )
            for match in related:
                edges.append(
                    GraphEdge(
                        id=f"match:{match.id}",
                        source=f"evidence:{match.evidence_id}",
                        target=key,
                        kind="matches",
                        weight=weight(match.rerank_score or 0),
                        status=match.status,
                        explanation=match.match_reason,
                    )
                )
    return EvidenceGraph(
        nodes=list(nodes.values()),
        edges=edges,
        job_id=str(job.id) if job else None,
        job_status=job.status if job else None,
        truncated=truncated,
        evidence_limit=limit,
    )
