"""Preserve source page title for browser/paste capture.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("source_title", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "source_title")
