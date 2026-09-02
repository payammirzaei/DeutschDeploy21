import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class SpeechConsent(Base):
    __tablename__ = "speech_consents"
    __table_args__ = (
        UniqueConstraint("user_id", "policy_version", name="uq_speech_consent_policy"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="CASCADE"), index=True
    )
    policy_version: Mapped[str] = mapped_column(String(40))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MediaObject(Base):
    __tablename__ = "media_objects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="CASCADE"), index=True
    )
    storage_backend: Mapped[str] = mapped_column(String(40), default="filesystem")
    storage_key: Mapped[str] = mapped_column(String(400), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    content_type: Mapped[str] = mapped_column(String(120))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SpeechAttempt(Base):
    __tablename__ = "speech_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="CASCADE"), index=True
    )
    enrollment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enrollments.id", ondelete="SET NULL"), nullable=True
    )
    source_kind: Mapped[str] = mapped_column(String(40), default="speaking_prompt")
    source_key: Mapped[str] = mapped_column(String(180), index=True)
    prompt: Mapped[dict] = mapped_column(JSON)
    prompt_checksum: Mapped[str] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(12), default="de")
    target_duration_seconds: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    media_object_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_objects.id", ondelete="RESTRICT"), nullable=True
    )
    transcription_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_jobs.id", ondelete="SET NULL"), nullable=True
    )
    transcription_retry_count: Mapped[int] = mapped_column(Integer, default=0)
    retry_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speech_attempts.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SpeechTranscript(Base):
    __tablename__ = "speech_transcripts"
    __table_args__ = (
        UniqueConstraint(
            "speech_attempt_id",
            "kind",
            "revision_number",
            name="uq_speech_transcript_revision",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    speech_attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speech_attempts.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32))
    revision_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(12), default="de")
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProviderInvocation(Base):
    __tablename__ = "provider_invocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    speech_attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speech_attempts.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(80))
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(160))
    template_version: Mapped[str] = mapped_column(String(40), default="v1")
    request_checksum: Mapped[str] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_microusd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retained_output_ref: Mapped[str | None] = mapped_column(String(180), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SpeechFeedback(Base):
    __tablename__ = "speech_feedback"
    __table_args__ = (
        UniqueConstraint(
            "transcript_id",
            "evaluator_type",
            "evaluator_version",
            name="uq_speech_feedback_evaluator",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    speech_attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speech_attempts.id", ondelete="CASCADE"), index=True
    )
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speech_transcripts.id", ondelete="RESTRICT")
    )
    evaluator_type: Mapped[str] = mapped_column(String(80), default="speech_text_heuristic")
    evaluator_version: Mapped[int] = mapped_column(Integer, default=1)
    overall_score: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text)
    dimensions: Mapped[dict] = mapped_column(JSON)
    corrections: Mapped[list] = mapped_column(JSON)
    next_action: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
