"""generalize release activities for full curriculum manifests

Revision ID: 20260902_0007
Revises: 20260902_0006
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260902_0007"
down_revision: str | None = "20260902_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "course_releases",
        sa.Column("manifest_checksum", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "release_activities",
        sa.Column(
            "source_kind",
            sa.String(length=40),
            nullable=False,
            server_default="content",
        ),
    )
    op.add_column(
        "release_activities",
        sa.Column("source_key", sa.String(length=180), nullable=True),
    )
    op.execute(
        "UPDATE release_activities "
        "SET source_key = content_version_id::text "
        "WHERE source_key IS NULL"
    )
    op.alter_column("release_activities", "source_key", nullable=False)
    op.alter_column("release_activities", "content_version_id", nullable=True)
    op.create_index(
        "ix_release_activity_source",
        "release_activities",
        ["source_kind", "source_key"],
    )
    op.alter_column("release_activities", "source_kind", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    non_content = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM release_activities "
            "WHERE content_version_id IS NULL"
        )
    ).scalar_one()
    if int(non_content) > 0:
        raise RuntimeError(
            "Cannot downgrade 0007 while non-content release activities exist. "
            "Remove or migrate full-curriculum releases first."
        )

    op.drop_index("ix_release_activity_source", table_name="release_activities")
    op.alter_column("release_activities", "content_version_id", nullable=False)
    op.drop_column("release_activities", "source_key")
    op.drop_column("release_activities", "source_kind")
    op.drop_column("course_releases", "manifest_checksum")
