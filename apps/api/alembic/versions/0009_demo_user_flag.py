"""Read-only guest/demo account flag.

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NOT NULL with a server default so the existing rows (all real users)
    # backfill to false without a separate data migration.
    op.add_column(
        "users",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "is_demo")
