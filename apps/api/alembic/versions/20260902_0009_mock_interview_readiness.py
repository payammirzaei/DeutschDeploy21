"""phase 7 mock interview sessions and readiness reports

Revision ID: 20260902_0009
Revises: 20260902_0008
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260902_0009"
down_revision: str | None = "20260902_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mock_interview_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identity_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("blueprint_key", sa.String(length=120), nullable=False),
        sa.Column("blueprint_version", sa.Integer(), nullable=False),
        sa.Column("blueprint_checksum", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=24), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("seed", sa.String(length=64), nullable=False),
        sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_turn_key", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_mock_interview_sessions_user_status",
        "mock_interview_sessions",
        ["user_id", "status"],
    )

    op.create_table(
        "mock_interview_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mock_interview_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position_key", sa.String(length=16), nullable=False),
        sa.Column("question_key", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("question", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_follow_up", sa.Boolean(), nullable=False),
        sa.Column(
            "parent_turn_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mock_interview_turns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("follow_up_reason", sa.String(length=80), nullable=True),
        sa.Column("hint_used", sa.Boolean(), nullable=False),
        sa.Column(
            "speech_attempt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("speech_attempts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("answer_source", sa.String(length=32), nullable=True),
        sa.Column("answer_idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "session_id",
            "position_key",
            name="uq_mock_interview_turn_position",
        ),
        sa.UniqueConstraint(
            "answer_idempotency_key",
            name="uq_mock_interview_answer_idempotency",
        ),
    )
    op.create_index(
        "ix_mock_interview_turns_session_status",
        "mock_interview_turns",
        ["session_id", "status"],
    )

    op.create_table(
        "mock_interview_turn_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "turn_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mock_interview_turns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rubric_version", sa.Integer(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "turn_id",
            "rubric_version",
            name="uq_mock_turn_evaluation_version",
        ),
    )

    op.create_table(
        "mock_readiness_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mock_interview_sessions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("rubric_version", sa.Integer(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("strengths", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("priorities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("comparison", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("mock_readiness_reports")
    op.drop_table("mock_interview_turn_evaluations")
    op.drop_index(
        "ix_mock_interview_turns_session_status",
        table_name="mock_interview_turns",
    )
    op.drop_table("mock_interview_turns")
    op.drop_index(
        "ix_mock_interview_sessions_user_status",
        table_name="mock_interview_sessions",
    )
    op.drop_table("mock_interview_sessions")
