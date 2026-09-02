"""phase 6 durable speech pipeline

Revision ID: 20260902_0008
Revises: 20260902_0007
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260902_0008"
down_revision: str | None = "20260902_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "speech_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "policy_version", name="uq_speech_consent_policy"),
    )
    op.create_index("ix_speech_consents_user", "speech_consents", ["user_id"])

    op.create_table(
        "media_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_key", sa.String(length=400), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_media_storage_key"),
    )
    op.create_index("ix_media_objects_user", "media_objects", ["user_id"])
    op.create_index("ix_media_objects_status", "media_objects", ["status"])

    op.create_table(
        "speech_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("source_key", sa.String(length=180), nullable=False),
        sa.Column("prompt", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prompt_checksum", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=12), nullable=False),
        sa.Column("target_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("media_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("transcription_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("transcription_retry_count", sa.Integer(), nullable=False),
        sa.Column("retry_of_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["media_object_id"], ["media_objects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["transcription_job_id"], ["platform_jobs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["retry_of_id"], ["speech_attempts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_speech_attempts_user", "speech_attempts", ["user_id"])
    op.create_index("ix_speech_attempts_status", "speech_attempts", ["status"])
    op.create_index(
        "ix_speech_attempts_source", "speech_attempts", ["source_kind", "source_key"]
    )

    op.create_table(
        "speech_transcripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("speech_attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=12), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("model", sa.String(length=160), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["speech_attempt_id"], ["speech_attempts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "speech_attempt_id",
            "kind",
            "revision_number",
            name="uq_speech_transcript_revision",
        ),
    )
    op.create_index(
        "ix_speech_transcripts_attempt", "speech_transcripts", ["speech_attempt_id"]
    )

    op.create_table(
        "provider_invocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("speech_attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("template_version", sa.String(length=40), nullable=False),
        sa.Column("request_checksum", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_units", sa.Integer(), nullable=True),
        sa.Column("output_units", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_microusd", sa.Integer(), nullable=True),
        sa.Column("retained_output_ref", sa.String(length=180), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["speech_attempt_id"], ["speech_attempts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("correlation_id", name="uq_provider_invocation_correlation"),
    )
    op.create_index(
        "ix_provider_invocations_attempt",
        "provider_invocations",
        ["speech_attempt_id"],
    )
    op.create_index(
        "ix_provider_invocations_status", "provider_invocations", ["status"]
    )

    op.create_table(
        "speech_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("speech_attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transcript_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluator_type", sa.String(length=80), nullable=False),
        sa.Column("evaluator_version", sa.Integer(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("corrections", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["speech_attempt_id"], ["speech_attempts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["transcript_id"], ["speech_transcripts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "transcript_id",
            "evaluator_type",
            "evaluator_version",
            name="uq_speech_feedback_evaluator",
        ),
    )
    op.create_index("ix_speech_feedback_attempt", "speech_feedback", ["speech_attempt_id"])


def downgrade() -> None:
    op.drop_index("ix_speech_feedback_attempt", table_name="speech_feedback")
    op.drop_table("speech_feedback")
    op.drop_index("ix_provider_invocations_status", table_name="provider_invocations")
    op.drop_index("ix_provider_invocations_attempt", table_name="provider_invocations")
    op.drop_table("provider_invocations")
    op.drop_index("ix_speech_transcripts_attempt", table_name="speech_transcripts")
    op.drop_table("speech_transcripts")
    op.drop_index("ix_speech_attempts_source", table_name="speech_attempts")
    op.drop_index("ix_speech_attempts_status", table_name="speech_attempts")
    op.drop_index("ix_speech_attempts_user", table_name="speech_attempts")
    op.drop_table("speech_attempts")
    op.drop_index("ix_media_objects_status", table_name="media_objects")
    op.drop_index("ix_media_objects_user", table_name="media_objects")
    op.drop_table("media_objects")
    op.drop_index("ix_speech_consents_user", table_name="speech_consents")
    op.drop_table("speech_consents")
