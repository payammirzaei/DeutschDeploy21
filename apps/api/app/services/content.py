import csv
import hashlib
import json
from pathlib import Path
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import (
    ContentDraft,
    ContentItem,
    ContentVersion,
    DraftExample,
    DraftLocalization,
    VerbDraft,
    VerbVersion,
    VersionExample,
    VersionLocalization,
)
from app.models.user import User
from app.schemas.content import (
    DraftVerbView,
    ExampleView,
    ImportApplyResult,
    ImportRowResult,
    PublishResult,
    VerbImportIn,
    VerbImportReport,
    VerbView,
    VersionSummary,
)


def payload_checksum(payload: VerbImportIn) -> str:
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def dry_run_verbs(session: AsyncSession, payloads: list[VerbImportIn]) -> VerbImportReport:
    _ensure_unique_external_ids(payloads)
    external_ids = [item.external_id for item in payloads]
    result = await session.execute(
        select(ContentItem, ContentDraft)
        .outerjoin(ContentDraft, ContentDraft.item_id == ContentItem.id)
        .where(ContentItem.external_id.in_(external_ids))
    )
    existing = {item.external_id: (item, draft) for item, draft in result.all()}

    rows: list[ImportRowResult] = []
    creates = updates = unchanged = 0
    for payload in payloads:
        checksum = payload_checksum(payload)
        current = existing.get(payload.external_id)
        if current is None:
            action = "create"
            creates += 1
        elif current[0].content_type != "verb":
            raise ValueError(
                f"{payload.external_id} already exists with type {current[0].content_type}"
            )
        elif current[1] is not None and current[1].source_checksum == checksum:
            action = "unchanged"
            unchanged += 1
        else:
            action = "update"
            updates += 1
        rows.append(
            ImportRowResult(
                external_id=payload.external_id,
                action=action,
                checksum=checksum,
            )
        )

    return VerbImportReport(
        total=len(rows),
        creates=creates,
        updates=updates,
        unchanged=unchanged,
        rows=rows,
    )


async def apply_verb_import(
    session: AsyncSession,
    actor: User,
    payloads: list[VerbImportIn],
) -> ImportApplyResult:
    report = await dry_run_verbs(session, payloads)
    actions = {row.external_id: row.action for row in report.rows}

    for payload in payloads:
        action = actions[payload.external_id]
        if action == "unchanged":
            continue

        item = await session.scalar(
            select(ContentItem).where(ContentItem.external_id == payload.external_id)
        )
        if item is None:
            item = ContentItem(
                external_id=payload.external_id,
                content_type="verb",
                status="draft",
                canonical_language=payload.canonical_language,
                created_by_user_id=actor.id,
            )
            session.add(item)
            await session.flush()
        else:
            item.status = "draft" if item.status != "published" else item.status
            item.canonical_language = payload.canonical_language

        checksum = payload_checksum(payload)
        draft = await session.get(ContentDraft, item.id)
        if draft is None:
            draft = ContentDraft(
                item_id=item.id,
                display_name=payload.display_infinitive or payload.lemma,
                definition=_primary_translation(payload, "en"),
                cefr=payload.classification.cefr,
                register=payload.classification.register,
                schema_version=1,
                source_checksum=checksum,
                updated_by_user_id=actor.id,
            )
            session.add(draft)
        else:
            draft.display_name = payload.display_infinitive or payload.lemma
            draft.definition = _primary_translation(payload, "en")
            draft.cefr = payload.classification.cefr
            draft.register = payload.classification.register
            draft.schema_version = 1
            draft.source_checksum = checksum
            draft.updated_by_user_id = actor.id

        verb = await session.get(VerbDraft, item.id)
        if verb is None:
            verb = VerbDraft(item_id=item.id)
            session.add(verb)
        _apply_verb_fields(verb, payload)

        await session.execute(
            delete(DraftLocalization).where(DraftLocalization.item_id == item.id)
        )
        await session.execute(delete(DraftExample).where(DraftExample.item_id == item.id))
        await session.flush()

        for locale, values in sorted(payload.translations.items()):
            for position, value in enumerate(values):
                session.add(
                    DraftLocalization(
                        item_id=item.id,
                        locale=locale,
                        field="translation",
                        position=position,
                        value=value.strip(),
                    )
                )

        for position, example in enumerate(payload.examples):
            session.add(
                DraftExample(
                    item_id=item.id,
                    external_id=example.external_id,
                    text_de=example.de.strip(),
                    text_fa=example.fa.strip() if example.fa else None,
                    text_en=example.en.strip() if example.en else None,
                    skill=example.skill,
                    sort_order=position,
                )
            )

    await session.flush()
    return ImportApplyResult(
        imported=report.creates + report.updates,
        created=report.creates,
        updated=report.updates,
        unchanged=report.unchanged,
    )


async def publish_item(session: AsyncSession, actor: User, item_id: UUID) -> PublishResult:
    item = await session.get(ContentItem, item_id)
    if item is None:
        raise LookupError("Content item not found")
    if item.content_type != "verb":
        raise ValueError("Only verb publishing is implemented in Phase 2")

    draft = await session.get(ContentDraft, item_id)
    verb = await session.get(VerbDraft, item_id)
    if draft is None or verb is None:
        raise ValueError("Content item has no complete verb draft")

    latest = await session.scalar(
        select(ContentVersion)
        .where(ContentVersion.item_id == item_id)
        .order_by(ContentVersion.version_number.desc())
        .limit(1)
    )
    if latest is not None and latest.checksum == draft.source_checksum:
        return PublishResult(
            item_id=item.id,
            external_id=item.external_id,
            version_id=latest.id,
            version_number=latest.version_number,
            checksum=latest.checksum,
            reused_existing_version=True,
        )

    version = ContentVersion(
        item_id=item.id,
        version_number=(latest.version_number + 1) if latest else 1,
        display_name=draft.display_name,
        definition=draft.definition,
        cefr=draft.cefr,
        register=draft.register,
        schema_version=draft.schema_version,
        checksum=draft.source_checksum,
        created_by_user_id=actor.id,
    )
    session.add(version)
    await session.flush()

    session.add(
        VerbVersion(
            version_id=version.id,
            lemma=verb.lemma,
            infinitive=verb.infinitive,
            perfect_auxiliary=verb.perfect_auxiliary,
            participle_ii=verb.participle_ii,
            preterite=verb.preterite,
            separable=verb.separable,
            separable_prefix=verb.separable_prefix,
            reflexive=verb.reflexive,
            regularity=verb.regularity,
            governed_case=verb.governed_case,
            governed_preposition=verb.governed_preposition,
        )
    )

    localizations = (
        await session.execute(
            select(DraftLocalization)
            .where(DraftLocalization.item_id == item_id)
            .order_by(
                DraftLocalization.locale,
                DraftLocalization.field,
                DraftLocalization.position,
            )
        )
    ).scalars()
    for localization in localizations:
        session.add(
            VersionLocalization(
                version_id=version.id,
                locale=localization.locale,
                field=localization.field,
                position=localization.position,
                value=localization.value,
            )
        )

    examples = (
        await session.execute(
            select(DraftExample)
            .where(DraftExample.item_id == item_id)
            .order_by(DraftExample.sort_order)
        )
    ).scalars()
    for example in examples:
        session.add(
            VersionExample(
                version_id=version.id,
                external_id=example.external_id,
                text_de=example.text_de,
                text_fa=example.text_fa,
                text_en=example.text_en,
                skill=example.skill,
                sort_order=example.sort_order,
            )
        )

    item.status = "published"
    await session.flush()
    return PublishResult(
        item_id=item.id,
        external_id=item.external_id,
        version_id=version.id,
        version_number=version.version_number,
        checksum=version.checksum,
    )


async def list_draft_verbs(session: AsyncSession) -> list[DraftVerbView]:
    rows = await session.execute(
        select(ContentItem, ContentDraft, VerbDraft)
        .join(ContentDraft, ContentDraft.item_id == ContentItem.id)
        .join(VerbDraft, VerbDraft.item_id == ContentItem.id)
        .where(ContentItem.content_type == "verb")
        .order_by(VerbDraft.lemma)
    )
    return [
        DraftVerbView(
            item_id=item.id,
            external_id=item.external_id,
            status=item.status,
            lemma=verb.lemma,
            cefr=draft.cefr,
            source_checksum=draft.source_checksum,
        )
        for item, draft, verb in rows.all()
    ]


async def list_published_verbs(session: AsyncSession) -> list[VerbView]:
    items = (
        await session.execute(
            select(ContentItem)
            .where(ContentItem.content_type == "verb", ContentItem.status == "published")
            .order_by(ContentItem.external_id)
        )
    ).scalars()

    result: list[VerbView] = []
    for item in items:
        latest = await session.scalar(
            select(ContentVersion)
            .where(ContentVersion.item_id == item.id)
            .order_by(ContentVersion.version_number.desc())
            .limit(1)
        )
        if latest is None:
            continue
        verb = await session.get(VerbVersion, latest.id)
        if verb is None:
            continue
        translations = await _version_translations(session, latest.id)
        examples = await _version_examples(session, latest.id)
        result.append(
            VerbView(
                item_id=item.id,
                external_id=item.external_id,
                version_id=latest.id,
                version_number=latest.version_number,
                lemma=verb.lemma,
                infinitive=verb.infinitive,
                perfect_auxiliary=verb.perfect_auxiliary,
                participle_ii=verb.participle_ii,
                preterite=verb.preterite,
                separable=verb.separable,
                separable_prefix=verb.separable_prefix,
                reflexive=verb.reflexive,
                regularity=verb.regularity,
                cefr=latest.cefr,
                register=latest.register,
                translations=translations,
                examples=examples,
            )
        )
    result.sort(key=lambda row: row.lemma)
    return result


async def list_versions(session: AsyncSession, item_id: UUID) -> list[VersionSummary]:
    versions = (
        await session.execute(
            select(ContentVersion)
            .where(ContentVersion.item_id == item_id)
            .order_by(ContentVersion.version_number.desc())
        )
    ).scalars()
    return [
        VersionSummary(
            version_id=version.id,
            version_number=version.version_number,
            checksum=version.checksum,
            published_at=version.published_at.isoformat(),
        )
        for version in versions
    ]


def load_starter_verbs() -> list[VerbImportIn]:
    path = Path(__file__).resolve().parents[4] / "content" / "starter-verbs.csv"
    records: list[dict] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            slug = row["external_id"].removeprefix("verb.")
            records.append(
                {
                    "external_id": row["external_id"],
                    "type": "verb",
                    "canonical_language": "de",
                    "lemma": row["lemma"],
                    "display_infinitive": row["lemma"],
                    "translations": {
                        "en": [row["translation_en"]],
                        "fa": [row["translation_fa"]],
                    },
                    "grammar": {
                        "perfect_auxiliary": row["perfect_auxiliary"],
                        "participle_ii": row["participle_ii"],
                        "preterite": None,
                        "separable": row["separable"].lower() == "true",
                        "separable_prefix": row["separable_prefix"] or None,
                        "reflexive": False,
                        "regularity": (
                            "regular"
                            if row["participle_ii"].endswith("t")
                            else "irregular"
                        ),
                        "governed_case": None,
                        "governed_preposition": None,
                    },
                    "classification": {
                        "cefr": row["cefr"],
                        "domains": ["software-development", "interview"],
                        "register": "neutral",
                    },
                    "examples": [
                        {
                            "external_id": f"example.{slug}.interview.1",
                            "de": row["example_de"],
                            "fa": None,
                            "en": None,
                            "skill": "technical-speaking",
                        }
                    ],
                }
            )
    return TypeAdapter(list[VerbImportIn]).validate_python(records)


async def _version_translations(
    session: AsyncSession,
    version_id: UUID,
) -> dict[str, list[str]]:
    rows = (
        await session.execute(
            select(VersionLocalization)
            .where(
                VersionLocalization.version_id == version_id,
                VersionLocalization.field == "translation",
            )
            .order_by(VersionLocalization.locale, VersionLocalization.position)
        )
    ).scalars()
    translations: dict[str, list[str]] = {}
    for row in rows:
        translations.setdefault(row.locale, []).append(row.value)
    return translations


async def _version_examples(session: AsyncSession, version_id: UUID) -> list[ExampleView]:
    rows = (
        await session.execute(
            select(VersionExample)
            .where(VersionExample.version_id == version_id)
            .order_by(VersionExample.sort_order)
        )
    ).scalars()
    return [
        ExampleView(
            external_id=row.external_id,
            de=row.text_de,
            fa=row.text_fa,
            en=row.text_en,
            skill=row.skill,
        )
        for row in rows
    ]


def _ensure_unique_external_ids(payloads: list[VerbImportIn]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in payloads:
        if item.external_id in seen:
            duplicates.add(item.external_id)
        seen.add(item.external_id)
    if duplicates:
        joined = ", ".join(sorted(duplicates))
        raise ValueError(f"duplicate external IDs: {joined}")


def _primary_translation(payload: VerbImportIn, locale: str) -> str | None:
    values = payload.translations.get(locale, [])
    return values[0].strip() if values else None


def _apply_verb_fields(model: VerbDraft, payload: VerbImportIn) -> None:
    model.lemma = payload.lemma.strip()
    model.infinitive = (payload.display_infinitive or payload.lemma).strip()
    model.perfect_auxiliary = payload.grammar.perfect_auxiliary
    model.participle_ii = payload.grammar.participle_ii.strip()
    model.preterite = payload.grammar.preterite.strip() if payload.grammar.preterite else None
    model.separable = payload.grammar.separable
    model.separable_prefix = payload.grammar.separable_prefix
    model.reflexive = payload.grammar.reflexive
    model.regularity = payload.grammar.regularity
    model.governed_case = payload.grammar.governed_case
    model.governed_preposition = payload.grammar.governed_preposition
