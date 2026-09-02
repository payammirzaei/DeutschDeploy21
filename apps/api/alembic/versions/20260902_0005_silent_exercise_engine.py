"""phase 5a silent exercise instance variants

Revision ID: 20260902_0005
Revises: 20260902_0004
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260902_0005"
down_revision: str | None = "20260902_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "activity_instances",
        sa.Column(
            "instance_key",
            sa.String(length=120),
            nullable=False,
            server_default="course",
        ),
    )
    op.drop_constraint(
        "uq_enrollment_activity_instance",
        "activity_instances",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_enrollment_activity_instance_key",
        "activity_instances",
        ["enrollment_id", "release_activity_id", "instance_key"],
    )
    op.alter_column(
        "activity_instances",
        "instance_key",
        server_default=None,
    )


def downgrade() -> None:
    op.execute("DELETE FROM activity_instances WHERE instance_key <> 'course'")
    op.drop_constraint(
        "uq_enrollment_activity_instance_key",
        "activity_instances",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_enrollment_activity_instance",
        "activity_instances",
        ["enrollment_id", "release_activity_id"],
    )
    op.drop_column("activity_instances", "instance_key")
