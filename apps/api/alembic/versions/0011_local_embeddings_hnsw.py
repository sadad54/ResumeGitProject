"""384-d embeddings with per-row model identity; HNSW instead of IVFFlat.

ADR-0018. The column was vector(1536), sized for OpenAI text-embedding-3-small,
which was the only real embedding provider; without an OpenAI key the vectors
were SHA-256 bytes with no semantic content. The default is now a local ONNX
model (bge-small-en-v1.5, 384-d), and OpenAI can be asked for 384 dims.

Existing vectors are cleared rather than converted: there is no meaningful
projection from 1536-d to 384-d, and in every database this has run against
they were either mock hashes or would be re-embedded anyway. The
`embedding_model` column records which model made each vector, and the
backfill (`python -m proofhire_worker.intelligence.reembed`) re-embeds every
row whose model is missing or not the configured one.

HNSW replaces IVFFlat because IVFFlat learns its cluster centroids when the
index is built: 0004 built it on an empty table, so it never had meaningful
lists, and rebuilding it on a populated table exceeded the default
maintenance_work_mem (OPERATIONS.md). HNSW needs no training step and stays
accurate as rows are inserted incrementally, which is how evidence arrives.

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_evidence_embedding_ivfflat")
    op.add_column("evidence", sa.Column("embedding_model", sa.String(100), nullable=True))
    op.execute("UPDATE evidence SET embedding = NULL WHERE embedding IS NOT NULL")
    op.execute("ALTER TABLE evidence ALTER COLUMN embedding TYPE vector(384)")
    op.execute(
        "CREATE INDEX ix_evidence_embedding_hnsw ON evidence "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_evidence_embedding_hnsw")
    op.execute("UPDATE evidence SET embedding = NULL WHERE embedding IS NOT NULL")
    op.execute("ALTER TABLE evidence ALTER COLUMN embedding TYPE vector(1536)")
    op.drop_column("evidence", "embedding_model")
    op.execute(
        "CREATE INDEX ix_evidence_embedding_ivfflat ON evidence "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
