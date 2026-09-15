import uuid
from datetime import datetime

from proofhire_contracts import GenerationRunStatus
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from proofhire_api.db import Base


class GenerationRun(Base):
    """PRD §13, §29. One row per end-to-end generation attempt — captures the
    observability data (prompt versions, token usage, cost, latency) that Phase
    9's eval reports and Phase 10's dashboards are built on."""

    __tablename__ = "generation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pipeline_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_config_json: Mapped[dict] = mapped_column("model_config", JSON, nullable=False, default=dict)
    prompt_versions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    token_usage: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[GenerationRunStatus] = mapped_column(
        String(20), nullable=False, default=GenerationRunStatus.QUEUED
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
