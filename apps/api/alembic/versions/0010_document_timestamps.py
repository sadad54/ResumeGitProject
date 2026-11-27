"""Audit timestamps on generated_documents.

The table had none, so GET /documents could only order by primary key — a
random UUID — and the "saved documents" list came back in arbitrary order.
`created_at` is backfilled from the generation run that produced each
document (the closest true value available); `exported_at` records the last
successful export so the UI can say when the stored files were made.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generated_documents",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE generated_documents AS d SET created_at = r.created_at "
        "FROM generation_runs AS r WHERE r.id = d.generation_run_id"
    )
    op.add_column(
        "generated_documents",
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Serves both the per-job listing and the newest-first user listing
    # (which joins through jobs on job_id).
    op.create_index(
        "ix_generated_documents_job_id_created_at",
        "generated_documents",
        ["job_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_generated_documents_job_id_created_at", table_name="generated_documents")
    op.drop_column("generated_documents", "exported_at")
    op.drop_column("generated_documents", "created_at")
