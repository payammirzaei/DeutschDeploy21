"""phase 3 curriculum release and deterministic learning runtime

Revision ID: 20260902_0003
Revises: 20260902_0002
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260902_0003"
down_revision: str | None = "20260902_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("target_language", sa.String(length=12), nullable=False),
        sa.Column("target_cefr", sa.String(length=20), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_courses_slug", "courses", ["slug"], unique=True)

    op.create_table(
        "course_releases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "version_number", name="uq_course_release_version"),
    )
    op.create_index("ix_course_releases_course_id", "course_releases", ["course_id"])
    op.create_index("ix_course_releases_status", "course_releases", ["status"])

    op.create_table(
        "course_days",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("objective", sa.String(length=600), nullable=False),
        sa.ForeignKeyConstraint(["release_id"], ["course_releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_id", "day_number", name="uq_course_release_day"),
    )
    op.create_index("ix_course_days_release_id", "course_days", ["release_id"])

    op.create_table(
        "release_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("exercise_type", sa.String(length=80), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("content_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["day_id"], ["course_days.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["content_version_id"],
            ["content_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day_id", "position", name="uq_release_activity_position"),
    )
    op.create_index("ix_release_activities_day_id", "release_activities", ["day_id"])
    op.create_index(
        "ix_release_activities_content_version_id",
        "release_activities",
        ["content_version_id"],
    )

    op.create_table(
        "enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_release_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_day", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["course_release_id"],
            ["course_releases.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "course_release_id", name="uq_user_course_release"),
    )
    op.create_index("ix_enrollments_user_id", "enrollments", ["user_id"])
    op.create_index("ix_enrollments_course_release_id", "enrollments", ["course_release_id"])
    op.create_index("ix_enrollments_status", "enrollments", ["status"])

    op.create_table(
        "activity_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_activity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exercise_type", sa.String(length=80), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.JSON(), nullable=False),
        sa.Column("answer_key", sa.JSON(), nullable=False),
        sa.Column("prompt_checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["release_activity_id"],
            ["release_activities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["content_version_id"],
            ["content_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "enrollment_id",
            "release_activity_id",
            name="uq_enrollment_activity_instance",
        ),
    )
    op.create_index("ix_activity_instances_enrollment_id", "activity_instances", ["enrollment_id"])
    op.create_index(
        "ix_activity_instances_release_activity_id",
        "activity_instances",
        ["release_activity_id"],
    )
    op.create_index(
        "ix_activity_instances_content_version_id",
        "activity_instances",
        ["content_version_id"],
    )
    op.create_index("ix_activity_instances_prompt_checksum", "activity_instances", ["prompt_checksum"])

    op.create_table(
        "attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("raw_answer", sa.JSON(), nullable=False),
        sa.Column("normalized_answer", sa.JSON(), nullable=False),
        sa.Column("client_duration_ms", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["activity_instance_id"],
            ["activity_instances.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_attempts_user_id", "attempts", ["user_id"])
    op.create_index("ix_attempts_enrollment_id", "attempts", ["enrollment_id"])
    op.create_index("ix_attempts_activity_instance_id", "attempts", ["activity_instance_id"])
    op.create_index("ix_attempts_idempotency_key", "attempts", ["idempotency_key"], unique=True)

    op.create_table(
        "evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluator_type", sa.String(length=40), nullable=False),
        sa.Column("evaluator_version", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("feedback_code", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id"),
    )
    op.create_index("ix_evaluations_attempt_id", "evaluations", ["attempt_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_evaluations_attempt_id", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_index("ix_attempts_idempotency_key", table_name="attempts")
    op.drop_index("ix_attempts_activity_instance_id", table_name="attempts")
    op.drop_index("ix_attempts_enrollment_id", table_name="attempts")
    op.drop_index("ix_attempts_user_id", table_name="attempts")
    op.drop_table("attempts")
    op.drop_index("ix_activity_instances_prompt_checksum", table_name="activity_instances")
    op.drop_index("ix_activity_instances_content_version_id", table_name="activity_instances")
    op.drop_index("ix_activity_instances_release_activity_id", table_name="activity_instances")
    op.drop_index("ix_activity_instances_enrollment_id", table_name="activity_instances")
    op.drop_table("activity_instances")
    op.drop_index("ix_enrollments_status", table_name="enrollments")
    op.drop_index("ix_enrollments_course_release_id", table_name="enrollments")
    op.drop_index("ix_enrollments_user_id", table_name="enrollments")
    op.drop_table("enrollments")
    op.drop_index("ix_release_activities_content_version_id", table_name="release_activities")
    op.drop_index("ix_release_activities_day_id", table_name="release_activities")
    op.drop_table("release_activities")
    op.drop_index("ix_course_days_release_id", table_name="course_days")
    op.drop_table("course_days")
    op.drop_index("ix_course_releases_status", table_name="course_releases")
    op.drop_index("ix_course_releases_course_id", table_name="course_releases")
    op.drop_table("course_releases")
    op.drop_index("ix_courses_slug", table_name="courses")
    op.drop_table("courses")
