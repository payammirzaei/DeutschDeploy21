import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    content_type: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    canonical_language: Mapped[str] = mapped_column(String(12), default="de")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContentDraft(Base):
    __tablename__ = "content_drafts"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str] = mapped_column(String(240))
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    cefr: Mapped[str] = mapped_column(String(4), index=True)
    register: Mapped[str] = mapped_column(String(32), default="neutral")
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    source_checksum: Mapped[str] = mapped_column(String(64))
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="RESTRICT")
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VerbDraft(Base):
    __tablename__ = "content_verb_drafts"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    lemma: Mapped[str] = mapped_column(String(120), index=True)
    infinitive: Mapped[str] = mapped_column(String(120))
    perfect_auxiliary: Mapped[str] = mapped_column(String(12))
    participle_ii: Mapped[str] = mapped_column(String(120))
    preterite: Mapped[str | None] = mapped_column(String(120), nullable=True)
    separable: Mapped[bool] = mapped_column(Boolean, default=False)
    separable_prefix: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reflexive: Mapped[bool] = mapped_column(Boolean, default=False)
    regularity: Mapped[str] = mapped_column(String(24), default="regular")
    governed_case: Mapped[str | None] = mapped_column(String(24), nullable=True)
    governed_preposition: Mapped[str | None] = mapped_column(String(80), nullable=True)


class DraftLocalization(Base):
    __tablename__ = "content_draft_localizations"
    __table_args__ = (
        UniqueConstraint("item_id", "locale", "field", "position", name="uq_draft_localization"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    locale: Mapped[str] = mapped_column(String(16))
    field: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer, default=0)
    value: Mapped[str] = mapped_column(Text)


class DraftExample(Base):
    __tablename__ = "content_draft_examples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(180), unique=True)
    text_de: Mapped[str] = mapped_column(Text)
    text_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class ContentVersion(Base):
    __tablename__ = "content_versions"
    __table_args__ = (
        UniqueConstraint("item_id", "version_number", name="uq_content_version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="RESTRICT"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    display_name: Mapped[str] = mapped_column(String(240))
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    cefr: Mapped[str] = mapped_column(String(4), index=True)
    register: Mapped[str] = mapped_column(String(32))
    schema_version: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VerbVersion(Base):
    __tablename__ = "content_verb_versions"

    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_versions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    lemma: Mapped[str] = mapped_column(String(120), index=True)
    infinitive: Mapped[str] = mapped_column(String(120))
    perfect_auxiliary: Mapped[str] = mapped_column(String(12))
    participle_ii: Mapped[str] = mapped_column(String(120))
    preterite: Mapped[str | None] = mapped_column(String(120), nullable=True)
    separable: Mapped[bool] = mapped_column(Boolean)
    separable_prefix: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reflexive: Mapped[bool] = mapped_column(Boolean)
    regularity: Mapped[str] = mapped_column(String(24))
    governed_case: Mapped[str | None] = mapped_column(String(24), nullable=True)
    governed_preposition: Mapped[str | None] = mapped_column(String(80), nullable=True)


class VersionLocalization(Base):
    __tablename__ = "content_version_localizations"
    __table_args__ = (
        UniqueConstraint(
            "version_id", "locale", "field", "position", name="uq_version_localization"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_versions.id", ondelete="CASCADE"), index=True
    )
    locale: Mapped[str] = mapped_column(String(16))
    field: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer, default=0)
    value: Mapped[str] = mapped_column(Text)


class VersionExample(Base):
    __tablename__ = "content_version_examples"
    __table_args__ = (
        UniqueConstraint("version_id", "external_id", name="uq_version_example_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_versions.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(180))
    text_de: Mapped[str] = mapped_column(Text)
    text_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
