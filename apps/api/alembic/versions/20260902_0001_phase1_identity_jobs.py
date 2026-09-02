"""phase 1 identity and platform jobs

Revision ID: 20260902_0001
Revises:
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260902_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identity_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_identity_users_email", "identity_users", ["email"], unique=True)

    op.create_table(
        "platform_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_platform_jobs_created_at", "platform_jobs", ["created_at"], unique=False)
    op.create_index(
        "ix_platform_jobs_idempotency_key", "platform_jobs", ["idempotency_key"], unique=True
    )
    op.create_index("ix_platform_jobs_job_type", "platform_jobs", ["job_type"], unique=False)
    op.create_index("ix_platform_jobs_status", "platform_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_platform_jobs_status", table_name="platform_jobs")
    op.drop_index("ix_platform_jobs_job_type", table_name="platform_jobs")
    op.drop_index("ix_platform_jobs_idempotency_key", table_name="platform_jobs")
    op.drop_index("ix_platform_jobs_created_at", table_name="platform_jobs")
    op.drop_table("platform_jobs")
    op.drop_index("ix_identity_users_email", table_name="identity_users")
    op.drop_table("identity_users")
