import uuid

from proofhire_contracts import ProfileFactType
from sqlalchemy import JSON, Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from proofhire_api.db import Base


class ProfileFact(Base):
    """PRD §13: user-confirmed facts GitHub can't establish (employment,
    education, awards, certifications). `immutable=True` facts (employer name,
    dates, degree) are exactly what the deterministic fact guard (Phase 5)
    checks generated claims against — they can never be paraphrased or altered
    by the writer, only cited verbatim."""

    __tablename__ = "profile_facts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[ProfileFactType] = mapped_column(String(30), nullable=False)
    value_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
