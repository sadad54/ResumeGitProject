"""Record rendered page count for overflow detection.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable: documents exported before this migration were never measured,
    # and backfilling would mean re-rendering every historical PDF. NULL
    # honestly means "unknown", which the UI can distinguish from "fits".
    op.add_column("generated_documents", sa.Column("page_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_documents", "page_count")
