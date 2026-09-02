# Phase 2 — Content and publishing implementation

**Status:** In implementation / CI verification  
**Branch:** `feat/phase-2-content-publishing`

## Outcome

Phase 2 turns the first learning material into versioned product data. A supported verb can be imported, validated, edited as a draft, published as an immutable version, corrected into a later version, and consumed by the web catalog without adding a React page or backend branch for that verb.

## Delivered vertical slice

```text
Controlled CSV / JSON request
        ↓
Pydantic structural + pedagogical validation
        ↓
Dry-run diff by external ID + canonical checksum
        ↓
Mutable PostgreSQL draft
        ↓
Explicit publish
        ↓
Immutable content version + verb version + localizations + examples
        ↓
Authenticated catalog API
        ↓
Next.js mobile catalog
```

## Persistence

The implementation deliberately keeps stable concepts relational instead of storing the content contract as an opaque JSONB document.

- `content_items` — stable logical identity such as `verb.entwickeln`;
- `content_drafts` — mutable common editorial fields and source checksum;
- `content_verb_drafts` — mutable typed verb grammar;
- `content_draft_localizations` — ordered localized values;
- `content_draft_examples` — reusable authored examples for the current draft;
- `content_versions` — immutable published common metadata;
- `content_verb_versions` — immutable typed verb grammar;
- `content_version_localizations` — immutable localized values;
- `content_version_examples` — immutable examples shown with that version.

Published rows are never updated by the import path. A changed draft creates the next version number. Historical curriculum and attempts can therefore reference an exact `content_versions.id` later without inheriting silent edits.

## API

Authenticated Phase 2 routes live under `/api/v1/content`:

- `GET /verbs` — latest published verb versions;
- `GET /drafts/verbs` — current verb drafts;
- `POST /import/verbs/dry-run` — validate and classify create/update/unchanged without writing;
- `POST /import/verbs/apply` — upsert drafts only;
- `POST /items/{item_id}/publish` — create an immutable version, idempotently reusing the latest version when the checksum is unchanged;
- `GET /items/{item_id}/versions` — publication history;
- `POST /starter-catalog` — private idempotent installation of the bundled starter dataset.

OpenAPI remains the contract source and CI regenerates the TypeScript client before lint/typecheck/build.

## Starter content

`content/starter-verbs.csv` contains 100 German verbs selected for software-development work and job interviews. Each row includes:

- stable external ID;
- German lemma;
- English and Persian meaning;
- Perfekt auxiliary and Partizip II;
- separability metadata;
- CEFR level;
- one German interview/technical speaking example.

The CSV is not special database seed SQL. It enters through the same typed content contract used by the API, so future corrections participate in normal checksum diffing and immutable publication.

CLI install is available with:

```bash
cd apps/api
uv run python -m app.scripts.seed_content
```

The private web catalog can install the same dataset when the catalog is empty.

## Verification

Integration coverage proves:

1. a new external ID dry-runs as `create`;
2. apply creates a mutable draft;
3. publish creates version 1;
4. changing translations/example content dry-runs/applies as an update;
5. publish creates version 2 with a different checksum;
6. version history still contains versions 2 and 1;
7. the learner-facing catalog resolves version 2;
8. starter installation publishes 100 verbs;
9. a second starter installation imports and publishes nothing.

CI also runs the existing Phase 1 worker path, so content work cannot silently break the platform skeleton.

## Known Phase 2 remainder

This slice intentionally does not yet build the full type-aware admin editor, arbitrary file upload UI, relationship graph, release manifests, or content-version diff screen. The foundations for those remain in the accepted content architecture. The immediate next delivery is the curriculum/learning-loop slice that consumes exact published versions; richer authoring UI can then be expanded against a real consumer instead of being built speculatively.

## Exit interpretation

Phase 2 is considered functionally proven when migration, Ruff, backend integration tests, OpenAPI generation, web lint/typecheck/build, starter 100-verb installation, and catalog rendering all pass. Railway staging remains an operational exit item shared with Phase 1 until infrastructure is provisioned.
