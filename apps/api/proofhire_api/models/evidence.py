import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from proofhire_contracts import EvidenceStatus, EvidenceType
from proofhire_contracts.embedding import EMBEDDING_DIMENSION
from sqlalchemy import DateTime, Float, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from proofhire_api.db import Base


class Evidence(Base):
    """PRD §13, §14. Every Evidence row MUST have at least one EvidenceSource
    (enforced at the application layer in EvidenceRepository.save_candidates —
    Postgres can't easily express "at least one child row" as a DB constraint)
    unless explicitly backed by a confirmed ProfileFact (added in Phase 5)."""

    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_type: Mapped[EvidenceType] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_claim: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[EvidenceStatus] = mapped_column(
        String(20), nullable=False, default=EvidenceStatus.CANDIDATE
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True
    )


class EvidenceSource(Base):
    """Many-to-many evidence provenance (PRD §13). One Evidence item may cite
    several SourceArtifacts; one SourceArtifact may support several Evidence
    items."""

    __tablename__ = "evidence_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    locator: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "path#L10-L42"
    snippet_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    line_start: Mapped[int | None] = mapped_column(nullable=True)
    line_end: Mapped[int | None] = mapped_column(nullable=True)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    relevance: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=1.0)


class EvidenceSkill(Base):
    __tablename__ = "evidence_skills"

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )
    strength: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=1.0)
