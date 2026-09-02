"""phase 4 mastery projection and spaced review

Revision ID: 20260902_0004
Revises: 20260902_0003
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260902_0004"
down_revision: str | None = "20260902_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_dimension", sa.String(length=80), nullable=False),
        sa.Column("production_mode", sa.String(length=40), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["content_version_id"],
            ["content_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_version_id",
            "skill_dimension",
            "production_mode",
            name="uq_learning_target_identity",
        ),
    )
    op.create_index(
        "ix_learning_targets_content_version_id",
        "learning_targets",
        ["content_version_id"],
    )

    op.create_table(
        "mastery_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("evidence_weight", sa.Float(), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["learning_targets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", name="uq_mastery_event_attempt"),
        sa.UniqueConstraint(
            "user_id",
            "event_sequence",
            name="uq_mastery_event_user_sequence",
        ),
    )
    op.create_index("ix_mastery_events_user_id", "mastery_events", ["user_id"])
    op.create_index("ix_mastery_events_target_id", "mastery_events", ["target_id"])

    op.create_table(
        "learner_mastery",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("stability", sa.Float(), nullable=False),
        sa.Column("difficulty", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("success_streak", sa.Integer(), nullable=False),
        sa.Column("lapses", sa.Integer(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_event_sequence", sa.Integer(), nullable=False),
        sa.Column("scheduler_version", sa.Integer(), nullable=False),
        sa.Column("explanation_code", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["learning_targets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "target_id", name="uq_learner_mastery_target"),
    )
    op.create_index("ix_learner_mastery_user_id", "learner_mastery", ["user_id"])
    op.create_index("ix_learner_mastery_next_review_at", "learner_mastery", ["next_review_at"])

    op.create_table(
        "review_queue_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("scheduler_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["learning_targets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["activity_instance_id"],
            ["activity_instances.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "target_id", name="uq_review_queue_target"),
    )
    op.create_index("ix_review_queue_entries_user_id", "review_queue_entries", ["user_id"])
    op.create_index("ix_review_queue_entries_due_at", "review_queue_entries", ["due_at"])


def downgrade() -> None:
    op.drop_index("ix_review_queue_entries_due_at", table_name="review_queue_entries")
    op.drop_index("ix_review_queue_entries_user_id", table_name="review_queue_entries")
    op.drop_table("review_queue_entries")
    op.drop_index("ix_learner_mastery_next_review_at", table_name="learner_mastery")
    op.drop_index("ix_learner_mastery_user_id", table_name="learner_mastery")
    op.drop_table("learner_mastery")
    op.drop_index("ix_mastery_events_target_id", table_name="mastery_events")
    op.drop_index("ix_mastery_events_user_id", table_name="mastery_events")
    op.drop_table("mastery_events")
    op.drop_index("ix_learning_targets_content_version_id", table_name="learning_targets")
    op.drop_table("learning_targets")
