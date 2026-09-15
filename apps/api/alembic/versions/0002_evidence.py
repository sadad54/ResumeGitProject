"""evidence graph: skills, evidence, evidence_sources, evidence_skills

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMENSION = 1536


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_name", sa.String(255), nullable=False, unique=True),
        sa.Column("aliases", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("category", sa.String(100), nullable=True),
    )

    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("evidence_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("normalized_claim", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("extraction_method", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="candidate"),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "superseded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_evidence_user_id", "evidence", ["user_id"])
    op.create_index("ix_evidence_repository_id", "evidence", ["repository_id"])

    op.create_table(
        "evidence_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("locator", sa.String(), nullable=False),
        sa.Column("snippet_hash", sa.String(64), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("relevance", sa.Numeric(4, 3), nullable=False, server_default="1.0"),
    )
    op.create_index("ix_evidence_sources_evidence_id", "evidence_sources", ["evidence_id"])
    op.create_index(
        "ix_evidence_sources_source_artifact_id", "evidence_sources", ["source_artifact_id"]
    )

    op.create_table(
        "evidence_skills",
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "skill_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("skills.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("strength", sa.Numeric(4, 3), nullable=False, server_default="1.0"),
    )


def downgrade() -> None:
    op.drop_table("evidence_skills")
    op.drop_index("ix_evidence_sources_source_artifact_id", table_name="evidence_sources")
    op.drop_index("ix_evidence_sources_evidence_id", table_name="evidence_sources")
    op.drop_table("evidence_sources")
    op.drop_index("ix_evidence_repository_id", table_name="evidence")
    op.drop_index("ix_evidence_user_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_table("skills")
