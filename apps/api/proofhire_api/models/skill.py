import uuid

from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from proofhire_api.db import Base


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
