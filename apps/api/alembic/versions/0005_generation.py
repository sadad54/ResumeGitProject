"""profile_facts, generation_runs, generated_documents, generated_claims, claim_evidence

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profile_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("immutable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_profile_facts_user_id", "profile_facts", ["user_id"])

    op.create_table(
        "generation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("pipeline_version", sa.String(50), nullable=False),
        sa.Column("model_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("prompt_versions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("token_usage", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_generation_runs_user_id", "generation_runs", ["user_id"])
    op.create_index("ix_generation_runs_job_id", "generation_runs", ["job_id"])

    op.create_table(
        "generated_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "generation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("template_id", sa.String(50), nullable=False, server_default="ats_minimal"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("html_ref", sa.String(), nullable=True),
        sa.Column("pdf_ref", sa.String(), nullable=True),
        sa.Column("plaintext_ref", sa.String(), nullable=True),
    )
    op.create_index("ix_generated_documents_job_id", "generated_documents", ["job_id"])

    op.create_table(
        "generated_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(30), nullable=False),
        sa.Column("verification_status", sa.String(25), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_index("ix_generated_claims_document_id", "generated_claims", ["document_id"])

    op.create_table(
        "claim_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_claims.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("support_score", sa.Numeric(4, 3), nullable=False, server_default="0"),
        sa.Column("verifier_reason", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_claim_evidence_claim_id", "claim_evidence", ["claim_id"])
    op.create_index("ix_claim_evidence_evidence_id", "claim_evidence", ["evidence_id"])


def downgrade() -> None:
    op.drop_table("claim_evidence")
    op.drop_index("ix_generated_claims_document_id", table_name="generated_claims")
    op.drop_table("generated_claims")
    op.drop_index("ix_generated_documents_job_id", table_name="generated_documents")
    op.drop_table("generated_documents")
    op.drop_index("ix_generation_runs_job_id", table_name="generation_runs")
    op.drop_index("ix_generation_runs_user_id", table_name="generation_runs")
    op.drop_table("generation_runs")
    op.drop_index("ix_profile_facts_user_id", table_name="profile_facts")
    op.drop_table("profile_facts")
