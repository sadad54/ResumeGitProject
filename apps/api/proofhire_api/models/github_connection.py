import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from proofhire_api.db import Base


class GitHubConnection(Base):
    """One row per user's connected GitHub account.

    `token_ref` stores the Fernet-encrypted OAuth token (see
    proofhire_api/security/token_crypto.py). The token is NEVER stored in plaintext
    (PRD §27) and is decrypted only transiently, in-process, when making a GitHub API
    call.
    """

    __tablename__ = "github_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    github_user_id: Mapped[int] = mapped_column(nullable=False)
    login: Mapped[str] = mapped_column(String(255), nullable=False)
    token_ref: Mapped[str] = mapped_column(String, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
