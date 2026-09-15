"""evidence_matches + hybrid retrieval indexes (search_vector GIN, embedding IVFFlat)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evidence_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "requirement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("requirements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("retrieval_score", sa.Float(), nullable=False),
        sa.Column("rerank_score", sa.Float(), nullable=True),
        sa.Column("match_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(10), nullable=False),
        sa.UniqueConstraint("requirement_id", "evidence_id", name="uq_match_requirement_evidence"),
    )
    op.create_index("ix_evidence_matches_requirement_id", "evidence_matches", ["requirement_id"])
    op.create_index("ix_evidence_matches_evidence_id", "evidence_matches", ["evidence_id"])

    # ADR-0006: lexical signal via generated tsvector + GIN index.
    op.execute(
        """
        ALTER TABLE evidence
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(normalized_claim, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'B')
        ) STORED
        """
    )
    op.execute("CREATE INDEX ix_evidence_search_vector ON evidence USING GIN (search_vector)")

    # ADR-0006: vector signal via IVFFlat cosine-distance index. Safe to create on
    # an empty/small table for V1 — Postgres will warn but not fail; revisit list
    # count once real row counts exist (Phase 9 eval data).
    op.execute(
        "CREATE INDEX ix_evidence_embedding_ivfflat ON evidence "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_evidence_embedding_ivfflat")
    op.execute("DROP INDEX IF EXISTS ix_evidence_search_vector")
    op.execute("ALTER TABLE evidence DROP COLUMN IF EXISTS search_vector")
    op.drop_index("ix_evidence_matches_evidence_id", table_name="evidence_matches")
    op.drop_index("ix_evidence_matches_requirement_id", table_name="evidence_matches")
    op.drop_table("evidence_matches")
