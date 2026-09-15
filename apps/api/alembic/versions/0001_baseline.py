"""baseline: users, github_connections, repositories, source_artifacts, sync_runs

Revision ID: 0001
Revises:
Create Date: 2026-09-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "github_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("github_user_id", sa.Integer(), nullable=False),
        sa.Column("login", sa.String(255), nullable=False),
        sa.Column("token_ref", sa.String(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_repo_id", sa.Integer(), nullable=False),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="public"),
        sa.Column("default_branch", sa.String(255), nullable=False, server_default="main"),
        sa.Column("language_summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("stars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_commit_sha", sa.String(40), nullable=True),
        sa.Column("last_analyzed_sha", sa.String(40), nullable=True),
        sa.Column("sync_status", sa.String(20), nullable=False, server_default="idle"),
        sa.UniqueConstraint("user_id", "provider_repo_id", name="uq_repo_user_provider"),
    )
    op.create_index("ix_repositories_user_id", "repositories", ["user_id"])

    op.create_table(
        "source_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("priority", sa.String(2), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("storage_ref", sa.String(), nullable=True),
        sa.UniqueConstraint(
            "repository_id", "path", "content_hash", name="uq_artifact_repo_path_hash"
        ),
    )
    op.create_index("ix_source_artifacts_repository_id", "source_artifacts", ["repository_id"])

    op.create_table(
        "sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("repository_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sync_runs_user_id", "sync_runs", ["user_id"])


def downgrade() -> None:
    op.drop_table("sync_runs")
    op.drop_index("ix_source_artifacts_repository_id", table_name="source_artifacts")
    op.drop_table("source_artifacts")
    op.drop_index("ix_repositories_user_id", table_name="repositories")
    op.drop_table("repositories")
    op.drop_table("github_connections")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
