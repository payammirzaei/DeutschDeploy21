# Testing and quality strategy

**Status:** Accepted baseline

## 1. Quality philosophy

Tests protect domain meaning, not only lines. The highest-risk areas are publishing/versioning, attempt durability, evaluation correctness, mastery scheduling, authorization, async idempotency, and provider boundaries.

## 2. Test layers

### Static
Type checking, linting, formatting, import/dependency-boundary rules, schema validation, migration linting, secret detection.

### Unit
Domain policies, linguistic normalization, exercise materialization/evaluation, mastery transitions, scheduling, scoring, permissions, and configuration.

### Property-based
Randomized invariants for conjugation normalization, word ordering, idempotency, scheduling bounds, version comparisons, and import round trips.

### Integration
Repositories against real PostgreSQL, Redis queue behavior, object storage adapter, transactions/outbox, migrations, and provider fakes.

### Contract
OpenAPI compatibility, frontend generated client, job payload versions, exercise instance schemas, provider adapters, and import formats.

### End-to-end
Sign-in, daily plan, exercise attempts, resume, content authoring, publishing, review, audio upload/processing, mock interview, and reports.

### Accessibility
Automated checks plus keyboard, screen-reader landmarks, focus, contrast, reduced motion, and non-drag alternatives.

### Performance
Dashboard, next activity, attempt submission, release materialization, imports, queue throughput, and large learner history.

### Security
Authentication/authorization, IDOR, CSRF, CORS, XSS, injection, upload limits, signed URLs, rate limits, and dependency/container scans.

## 3. Test pyramid

Most deterministic domain behavior belongs in fast unit/property tests. Integration tests verify infrastructure semantics. A focused E2E suite covers critical journeys; avoid encoding every content variation in fragile browser tests.

## 4. Content tests

Published content is testable data. CI/release validation checks required fields, linguistic rules, relationships, ambiguity, duplicate external IDs, exercise compatibility, translations, source/license metadata, curriculum workload, and rubric availability.

Snapshot tests may help review activity previews but cannot replace semantic assertions.

## 5. Golden datasets

Maintain reviewed fixtures for verbs, examples, accepted variants, ambiguous cases, interview answers at several quality levels, transcripts with technical terms, and provider failures.

Golden cases have stable IDs, expected dimensions, tolerance, reviewer notes, and applicable evaluator versions.

## 6. AI evaluation tests

Measure structured-output validity, factual preservation, correction accuracy, evidence grounding, score agreement, bias, refusal behavior, prompt injection resistance, latency, and cost.

Model changes run against benchmarks. Non-deterministic outputs use ranges and semantic invariants, not brittle exact snapshots.

## 7. Speech tests

Use consented/synthetic samples spanning clear speech, accent variation, background noise, code-switching, technical vocabulary, silence, short audio, oversized audio, and corrupted files.

Test upload state transitions separately from provider quality.

## 8. Migration tests

Start from previous production-like schema, apply migrations, verify constraints/data, boot old/new compatible app versions where required, and test corrective path. High-risk migrations require backup/restore rehearsal.

## 9. Reliability tests

Inject provider timeout, malformed response, Redis interruption, worker crash after provider charge, duplicate delivery, storage failure, database deadlock, and frontend retry. Verify idempotency and visible recovery state.

## 10. Fixtures and seeds

Seeds are deterministic, environment-aware, idempotent, and contain no production personal data. Tests create isolated users/enrollments and never rely on execution order.

## 11. CI gates

Pull request minimum:

- format/lint/types;
- unit/property;
- contract/schema;
- database integration and migrations;
- content validation;
- security/secret scan;
- critical accessibility checks;
- build all deployable artifacts.

Main/release adds E2E, container scan, smoke tests, and migration validation.

## 12. Manual release checklist

Mobile viewport, install/PWA update, Persian/German direction, keyboard flow, representative lesson, failure messages, recording consent/upload/deletion, admin preview/publish, readiness explanation, provider-offline mode, and Railway health.

## 13. Defect severity

- **S0:** active security/privacy compromise or destructive data corruption.
- **S1:** core learning unusable, attempts lost, publish corruption.
- **S2:** major feature broken with workaround.
- **S3:** limited defect or degraded experience.
- **S4:** cosmetic/editorial issue.

Release policy defines blocking severities and hotfix path.

## 14. Definition of done

Requirement and UX accepted; domain boundaries respected; migrations safe; tests added; accessibility considered; errors observable; security/privacy reviewed; docs updated; metrics/events defined; rollback/recovery understood; preview/staging verified.
