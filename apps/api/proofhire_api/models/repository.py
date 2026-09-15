import uuid

from proofhire_contracts import SyncStatus
from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from proofhire_api.db import Base


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("user_id", "provider_repo_id", name="uq_repo_user_provider"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_repo_id: Mapped[int] = mapped_column(nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="public")
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    language_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    stars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_analyzed_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sync_status: Mapped[SyncStatus] = mapped_column(
        String(20), nullable=False, default=SyncStatus.IDLE
    )
