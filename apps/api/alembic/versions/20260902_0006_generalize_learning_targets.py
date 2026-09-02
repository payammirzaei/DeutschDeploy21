"""generalize activity instances and mastery targets for interview drills

Revision ID: 20260902_0006
Revises: 20260902_0005
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260902_0006"
down_revision: str | None = "20260902_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "activity_instances",
        sa.Column(
            "source_kind",
            sa.String(length=40),
            nullable=False,
            server_default="release_activity",
        ),
    )
    op.add_column(
        "activity_instances",
        sa.Column("source_key", sa.String(length=180), nullable=True),
    )
    op.execute(
        "UPDATE activity_instances "
        "SET source_key = release_activity_id::text "
        "WHERE source_key IS NULL"
    )
    op.alter_column("activity_instances", "source_key", nullable=False)
    op.drop_constraint(
        "uq_enrollment_activity_instance_key",
        "activity_instances",
        type_="unique",
    )
    op.alter_column("activity_instances", "release_activity_id", nullable=True)
    op.alter_column("activity_instances", "content_version_id", nullable=True)
    op.create_unique_constraint(
        "uq_enrollment_source_instance",
        "activity_instances",
        ["enrollment_id", "source_kind", "source_key", "instance_key"],
    )
    op.alter_column("activity_instances", "source_kind", server_default=None)

    op.add_column(
        "learning_targets",
        sa.Column("target_key", sa.String(length=220), nullable=True),
    )
    op.add_column(
        "learning_targets",
        sa.Column("target_label", sa.String(length=240), nullable=True),
    )
    op.add_column(
        "learning_targets",
        sa.Column(
            "target_kind",
            sa.String(length=40),
            nullable=False,
            server_default="content",
        ),
    )
    op.execute(
        "UPDATE learning_targets SET target_key = "
        "'content:' || content_version_id::text || ':' || skill_dimension || ':' || production_mode "
        "WHERE target_key IS NULL"
    )
    op.alter_column("learning_targets", "target_key", nullable=False)
    op.alter_column("learning_targets", "content_version_id", nullable=True)
    op.create_unique_constraint(
        "uq_learning_target_key",
        "learning_targets",
        ["target_key"],
    )
    op.alter_column("learning_targets", "target_kind", server_default=None)


def downgrade() -> None:
    op.execute(
        "DELETE FROM review_queue_entries WHERE target_id IN "
        "(SELECT id FROM learning_targets WHERE target_kind <> 'content')"
    )
    op.execute(
        "DELETE FROM learner_mastery WHERE target_id IN "
        "(SELECT id FROM learning_targets WHERE target_kind <> 'content')"
    )
    op.execute(
        "DELETE FROM mastery_events WHERE target_id IN "
        "(SELECT id FROM learning_targets WHERE target_kind <> 'content')"
    )
    op.execute(
        "DELETE FROM evaluations WHERE attempt_id IN ("
        "SELECT a.id FROM attempts a JOIN activity_instances i "
        "ON i.id = a.activity_instance_id WHERE i.source_kind <> 'release_activity')"
    )
    op.execute(
        "DELETE FROM attempts WHERE activity_instance_id IN "
        "(SELECT id FROM activity_instances WHERE source_kind <> 'release_activity')"
    )
    op.execute("DELETE FROM activity_instances WHERE source_kind <> 'release_activity'")
    op.execute("DELETE FROM learning_targets WHERE target_kind <> 'content'")

    op.drop_constraint("uq_learning_target_key", "learning_targets", type_="unique")
    op.alter_column("learning_targets", "content_version_id", nullable=False)
    op.drop_column("learning_targets", "target_kind")
    op.drop_column("learning_targets", "target_label")
    op.drop_column("learning_targets", "target_key")

    op.drop_constraint(
        "uq_enrollment_source_instance",
        "activity_instances",
        type_="unique",
    )
    op.alter_column("activity_instances", "release_activity_id", nullable=False)
    op.alter_column("activity_instances", "content_version_id", nullable=False)
    op.create_unique_constraint(
        "uq_enrollment_activity_instance_key",
        "activity_instances",
        ["enrollment_id", "release_activity_id", "instance_key"],
    )
    op.drop_column("activity_instances", "source_key")
    op.drop_column("activity_instances", "source_kind")
