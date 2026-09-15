import uuid

from proofhire_contracts import ClaimVerificationStatus
from sqlalchemy import Float, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from proofhire_api.db import Base


class GeneratedClaim(Base):
    __tablename__ = "generated_claims"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(30), nullable=False)  # e.g. skill, metric, employment
    verification_status: Mapped[ClaimVerificationStatus] = mapped_column(String(25), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class ClaimEvidence(Base):
    """PRD §13: which Evidence supports a given GeneratedClaim, and how well.
    Only for Evidence-grounded claims (skills, technologies, achievements) — a
    claim citing an immutable ProfileFact (employer, dates, degree) is checked
    directly by the deterministic fact guard instead, since that's exact-match
    validation against already-confirmed data, not evidence-retrieval-based
    verification."""

    __tablename__ = "claim_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    support_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.0)
    verifier_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
