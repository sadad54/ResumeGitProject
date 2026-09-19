import uuid

from proofhire_contracts import DocumentType
from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from proofhire_api.db import Base


class GeneratedDocument(Base):
    """PRD §13. Deviates slightly from the PRD's `application_id` FK: Application
    doesn't exist until Phase 6, so this references `job_id` directly for now.
    Phase 6 can add `application_id` alongside once Application lands, without
    needing to change this table's meaning."""

    __tablename__ = "generated_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generation_runs.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[DocumentType] = mapped_column(String(20), nullable=False)
    template_id: Mapped[str] = mapped_column(String(50), nullable=False, default="ats_minimal")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    html_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    pdf_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    plaintext_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    # Measured from the rendered PDF at export time, so the UI can warn about a
    # resume that has quietly spilled onto a second page.
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
