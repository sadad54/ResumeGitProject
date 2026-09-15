"""jobs and requirements

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("role", sa.String(255), nullable=True),
        sa.Column("seniority", sa.String(50), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="captured"),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])

    op.create_table(
        "requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.create_index("ix_requirements_job_id", "requirements", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_requirements_job_id", table_name="requirements")
    op.drop_table("requirements")
    op.drop_index("ix_jobs_user_id", table_name="jobs")
    op.drop_table("jobs")
