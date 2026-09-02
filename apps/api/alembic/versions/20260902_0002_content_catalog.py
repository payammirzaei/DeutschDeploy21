"""phase 2 content catalog and immutable publishing

Revision ID: 20260902_0002
Revises: 20260902_0001
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260902_0002"
down_revision: str | None = "20260902_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(length=180), nullable=False),
        sa.Column("content_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("canonical_language", sa.String(length=12), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["identity_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_content_items_content_type", "content_items", ["content_type"])
    op.create_index("ix_content_items_external_id", "content_items", ["external_id"], unique=True)
    op.create_index("ix_content_items_status", "content_items", ["status"])

    op.create_table(
        "content_drafts",
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=240), nullable=False),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.Column("cefr", sa.String(length=4), nullable=False),
        sa.Column("register", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["identity_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("item_id"),
    )
    op.create_index("ix_content_drafts_cefr", "content_drafts", ["cefr"])

    op.create_table(
        "content_verb_drafts",
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lemma", sa.String(length=120), nullable=False),
        sa.Column("infinitive", sa.String(length=120), nullable=False),
        sa.Column("perfect_auxiliary", sa.String(length=12), nullable=False),
        sa.Column("participle_ii", sa.String(length=120), nullable=False),
        sa.Column("preterite", sa.String(length=120), nullable=True),
        sa.Column("separable", sa.Boolean(), nullable=False),
        sa.Column("separable_prefix", sa.String(length=40), nullable=True),
        sa.Column("reflexive", sa.Boolean(), nullable=False),
        sa.Column("regularity", sa.String(length=24), nullable=False),
        sa.Column("governed_case", sa.String(length=24), nullable=True),
        sa.Column("governed_preposition", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("item_id"),
    )
    op.create_index("ix_content_verb_drafts_lemma", "content_verb_drafts", ["lemma"])

    op.create_table(
        "content_draft_localizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("field", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", "locale", "field", "position", name="uq_draft_localization"),
    )
    op.create_index("ix_content_draft_localizations_item_id", "content_draft_localizations", ["item_id"])

    op.create_table(
        "content_draft_examples",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(length=180), nullable=False),
        sa.Column("text_de", sa.Text(), nullable=False),
        sa.Column("text_fa", sa.Text(), nullable=True),
        sa.Column("text_en", sa.Text(), nullable=True),
        sa.Column("skill", sa.String(length=120), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_content_draft_examples_item_id", "content_draft_examples", ["item_id"])

    op.create_table(
        "content_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=240), nullable=False),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.Column("cefr", sa.String(length=4), nullable=False),
        sa.Column("register", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["content_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["identity_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", "version_number", name="uq_content_version_number"),
    )
    op.create_index("ix_content_versions_cefr", "content_versions", ["cefr"])
    op.create_index("ix_content_versions_checksum", "content_versions", ["checksum"])
    op.create_index("ix_content_versions_item_id", "content_versions", ["item_id"])

    op.create_table(
        "content_verb_versions",
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lemma", sa.String(length=120), nullable=False),
        sa.Column("infinitive", sa.String(length=120), nullable=False),
        sa.Column("perfect_auxiliary", sa.String(length=12), nullable=False),
        sa.Column("participle_ii", sa.String(length=120), nullable=False),
        sa.Column("preterite", sa.String(length=120), nullable=True),
        sa.Column("separable", sa.Boolean(), nullable=False),
        sa.Column("separable_prefix", sa.String(length=40), nullable=True),
        sa.Column("reflexive", sa.Boolean(), nullable=False),
        sa.Column("regularity", sa.String(length=24), nullable=False),
        sa.Column("governed_case", sa.String(length=24), nullable=True),
        sa.Column("governed_preposition", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["version_id"], ["content_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("version_id"),
    )
    op.create_index("ix_content_verb_versions_lemma", "content_verb_versions", ["lemma"])

    op.create_table(
        "content_version_localizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("field", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["content_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "locale", "field", "position", name="uq_version_localization"),
    )
    op.create_index("ix_content_version_localizations_version_id", "content_version_localizations", ["version_id"])

    op.create_table(
        "content_version_examples",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(length=180), nullable=False),
        sa.Column("text_de", sa.Text(), nullable=False),
        sa.Column("text_fa", sa.Text(), nullable=True),
        sa.Column("text_en", sa.Text(), nullable=True),
        sa.Column("skill", sa.String(length=120), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["content_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "external_id", name="uq_version_example_external"),
    )
    op.create_index("ix_content_version_examples_version_id", "content_version_examples", ["version_id"])


def downgrade() -> None:
    op.drop_index("ix_content_version_examples_version_id", table_name="content_version_examples")
    op.drop_table("content_version_examples")
    op.drop_index("ix_content_version_localizations_version_id", table_name="content_version_localizations")
    op.drop_table("content_version_localizations")
    op.drop_index("ix_content_verb_versions_lemma", table_name="content_verb_versions")
    op.drop_table("content_verb_versions")
    op.drop_index("ix_content_versions_item_id", table_name="content_versions")
    op.drop_index("ix_content_versions_checksum", table_name="content_versions")
    op.drop_index("ix_content_versions_cefr", table_name="content_versions")
    op.drop_table("content_versions")
    op.drop_index("ix_content_draft_examples_item_id", table_name="content_draft_examples")
    op.drop_table("content_draft_examples")
    op.drop_index("ix_content_draft_localizations_item_id", table_name="content_draft_localizations")
    op.drop_table("content_draft_localizations")
    op.drop_index("ix_content_verb_drafts_lemma", table_name="content_verb_drafts")
    op.drop_table("content_verb_drafts")
    op.drop_index("ix_content_drafts_cefr", table_name="content_drafts")
    op.drop_table("content_drafts")
    op.drop_index("ix_content_items_status", table_name="content_items")
    op.drop_index("ix_content_items_external_id", table_name="content_items")
    op.drop_index("ix_content_items_content_type", table_name="content_items")
    op.drop_table("content_items")
