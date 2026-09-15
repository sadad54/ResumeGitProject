import uuid
from datetime import datetime

from proofhire_contracts import SyncStatus
from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from proofhire_api.db import Base


class SyncRun(Base):
    """Tracks one `POST /github/sync` invocation across one or more repositories.

    `GET /github/sync/{run_id}` reads this row; the SSE stream at
    `GET /events/runs/{run_id}` mirrors its progress in near-real-time via Redis
    pub/sub (see proofhire_api/routers/events.py).
    """

    __tablename__ = "sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[SyncStatus] = mapped_column(String(20), nullable=False, default=SyncStatus.QUEUED)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
