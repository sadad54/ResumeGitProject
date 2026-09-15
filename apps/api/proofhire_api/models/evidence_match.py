import uuid

from proofhire_contracts import MatchLabel
from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from proofhire_api.db import Base


class EvidenceMatch(Base):
    """PRD §13, §17-18. One row per (requirement, evidence) pairing the coverage
    engine judged worth recording — not every candidate the retriever considered,
    only the ones a match label was assigned to."""

    __tablename__ = "evidence_matches"
    __table_args__ = (
        UniqueConstraint("requirement_id", "evidence_id", name="uq_match_requirement_evidence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    retrieval_score: Mapped[float] = mapped_column(Float, nullable=False)
    rerank_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[MatchLabel] = mapped_column(String(10), nullable=False)
