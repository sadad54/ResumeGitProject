import uuid

from proofhire_contracts import ArtifactPriority, SourceArtifactType
from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from proofhire_api.db import Base


class SourceArtifact(Base):
    """Represents one analyzable source within a repository (PRD §13, §15 Stage 2).

    The unique constraint on (repository_id, path, content_hash) is what makes
    incremental sync idempotent: re-syncing a repo where a file's content hasn't
    changed is a no-op insert-if-absent, not a duplicate row.
    """

    __tablename__ = "source_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "repository_id", "path", "content_hash", name="uq_artifact_repo_path_hash"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[SourceArtifactType] = mapped_column(String(30), nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    priority: Mapped[ArtifactPriority] = mapped_column(String(2), nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    storage_ref: Mapped[str | None] = mapped_column(String, nullable=True)
