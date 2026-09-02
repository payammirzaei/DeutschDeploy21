import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class MockInterviewSession(Base):
    __tablename__ = "mock_interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="CASCADE"), index=True
    )
    blueprint_key: Mapped[str] = mapped_column(String(120))
    blueprint_version: Mapped[int] = mapped_column(Integer)
    blueprint_checksum: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(24))
    purpose: Mapped[str] = mapped_column(String(24))
    seed: Mapped[str] = mapped_column(String(64))
    plan: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    current_turn_key: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MockInterviewTurn(Base):
    __tablename__ = "mock_interview_turns"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "position_key",
            name="uq_mock_interview_turn_position",
        ),
        UniqueConstraint(
            "answer_idempotency_key",
            name="uq_mock_interview_answer_idempotency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mock_interview_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    position_key: Mapped[str] = mapped_column(String(16))
    question_key: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40))
    question: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    is_follow_up: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_turn_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mock_interview_turns.id", ondelete="SET NULL"),
        nullable=True,
    )
    follow_up_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    hint_used: Mapped[bool] = mapped_column(Boolean, default=False)
    speech_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("speech_attempts.id", ondelete="SET NULL"),
        nullable=True,
    )
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    answer_idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MockInterviewTurnEvaluation(Base):
    __tablename__ = "mock_interview_turn_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "turn_id",
            "rubric_version",
            name="uq_mock_turn_evaluation_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    turn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mock_interview_turns.id", ondelete="CASCADE"),
        index=True,
    )
    rubric_version: Mapped[int] = mapped_column(Integer, default=1)
    overall_score: Mapped[int] = mapped_column(Integer)
    dimensions: Mapped[dict] = mapped_column(JSON)
    evidence: Mapped[dict] = mapped_column(JSON)
    summary: Mapped[str] = mapped_column(Text)
    next_action: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MockReadinessReport(Base):
    __tablename__ = "mock_readiness_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mock_interview_sessions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    rubric_version: Mapped[int] = mapped_column(Integer, default=1)
    overall_score: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)
    dimensions: Mapped[dict] = mapped_column(JSON)
    strengths: Mapped[list] = mapped_column(JSON)
    priorities: Mapped[list] = mapped_column(JSON)
    comparison: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
