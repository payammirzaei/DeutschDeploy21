import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(240))
    target_language: Mapped[str] = mapped_column(String(12), default="de")
    target_cefr: Mapped[str] = mapped_column(String(20), default="A2-B1")
    duration_days: Mapped[int] = mapped_column(Integer, default=21)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CourseRelease(Base):
    __tablename__ = "course_releases"
    __table_args__ = (
        UniqueConstraint("course_id", "version_number", name="uq_course_release_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="RESTRICT"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="published", index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CourseDay(Base):
    __tablename__ = "course_days"
    __table_args__ = (UniqueConstraint("release_id", "day_number", name="uq_course_release_day"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("course_releases.id", ondelete="CASCADE"), index=True
    )
    day_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(240))
    objective: Mapped[str] = mapped_column(String(600))


class ReleaseActivity(Base):
    __tablename__ = "release_activities"
    __table_args__ = (UniqueConstraint("day_id", "position", name="uq_release_activity_position"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    day_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("course_days.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    exercise_type: Mapped[str] = mapped_column(String(80), default="meaning_multiple_choice")
    contract_version: Mapped[int] = mapped_column(Integer, default=1)
    content_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_versions.id", ondelete="RESTRICT"), index=True
    )
    required: Mapped[bool] = mapped_column(Boolean, default=True)


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("user_id", "course_release_id", name="uq_user_course_release"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="CASCADE"), index=True
    )
    course_release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("course_releases.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    current_day: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ActivityInstance(Base):
    __tablename__ = "activity_instances"
    __table_args__ = (
        UniqueConstraint(
            "enrollment_id",
            "release_activity_id",
            "instance_key",
            name="uq_enrollment_activity_instance_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enrollments.id", ondelete="CASCADE"), index=True
    )
    release_activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("release_activities.id", ondelete="RESTRICT"), index=True
    )
    instance_key: Mapped[str] = mapped_column(String(120), default="course")
    content_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_versions.id", ondelete="RESTRICT"), index=True
    )
    exercise_type: Mapped[str] = mapped_column(String(80))
    contract_version: Mapped[int] = mapped_column(Integer)
    prompt: Mapped[dict] = mapped_column(JSON)
    answer_key: Mapped[dict] = mapped_column(JSON)
    prompt_checksum: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="CASCADE"), index=True
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enrollments.id", ondelete="CASCADE"), index=True
    )
    activity_instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_instances.id", ondelete="RESTRICT"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    raw_answer: Mapped[dict] = mapped_column(JSON)
    normalized_answer: Mapped[dict] = mapped_column(JSON)
    client_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attempts.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    evaluator_type: Mapped[str] = mapped_column(String(40), default="deterministic")
    evaluator_version: Mapped[int] = mapped_column(Integer, default=1)
    correct: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[int] = mapped_column(Integer)
    feedback_code: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
