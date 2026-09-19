"""Evidence staleness on repository change (PRD §15 Stage 8, checklist §1/§2).

A sync creates a *new* `SourceArtifact` row when a path's content hash changes,
leaving the previous row in place (the unique constraint is on
`(repository_id, path, content_hash)`). Evidence extracted earlier still points
at the superseded row, so without this step a confirmed evidence item would keep
citing a snippet that no longer exists at that commit — provenance that silently
stopped being true.

Marking `stale` rather than deleting is deliberate (ADR-0016): the user may have
already confirmed this evidence, and a re-extraction should be able to
re-verify it against the new content instead of discarding their decision.
"""

from __future__ import annotations

import uuid

from proofhire_contracts import EvidenceStatus
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.models.evidence import Evidence, EvidenceSource


async def mark_evidence_stale_for_artifacts(
    session: AsyncSession, superseded_artifact_ids: list[uuid.UUID]
) -> int:
    """Mark evidence sourced from superseded artifacts as stale.

    Only `candidate` and `confirmed` evidence is touched: `rejected` stays
    rejected (the user's decision stands), and `private` stays private (marking
    it stale would quietly change a privacy choice into a review-queue item).

    Returns the number of evidence rows marked.
    """
    if not superseded_artifact_ids:
        return 0

    affected = await session.scalars(
        select(EvidenceSource.evidence_id).where(
            EvidenceSource.source_artifact_id.in_(superseded_artifact_ids)
        )
    )
    evidence_ids = list({row for row in affected.all()})
    if not evidence_ids:
        return 0

    result = await session.execute(
        update(Evidence)
        .where(
            Evidence.id.in_(evidence_ids),
            Evidence.status.in_([EvidenceStatus.CANDIDATE, EvidenceStatus.CONFIRMED]),
        )
        .values(status=EvidenceStatus.STALE)
    )
    return result.rowcount or 0
