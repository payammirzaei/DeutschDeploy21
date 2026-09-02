# Development rules

**Status:** Accepted baseline

## 1. Core rule

Optimize local implementation for current scope while preserving explicit domain seams needed for future scope. Avoid both speculative abstraction and hard-coded shortcuts that destroy content, progress, or provider portability.

## 2. Repository practices

- Main must remain deployable.
- Work through focused branches and pull requests.
- Conventional commit style is preferred.
- Lockfiles are committed.
- Generated code is clearly marked.
- Do not commit secrets, production exports, recordings, or personal CV data.
- Each application/package owns a README once scaffolded.
- Architecture-impacting changes include an ADR.

## 3. Backend boundaries

HTTP routes validate/translate and invoke use cases. Business rules live in domain/application code. Repository interfaces are owned inward; infrastructure implements them. Transactions are explicit. No raw cross-module table access from unrelated modules.

## 4. Frontend boundaries

Routes compose features. Feature modules own queries/forms/state. Shared UI remains domain-neutral. API access uses generated/typed clients. Do not duplicate scoring, permission, or schedule rules in components.

## 5. Content rule

No production lesson, verb, question, accepted answer, learner biography, or curriculum ordering is hard-coded in UI/backend branching. Seed/import files are data and pass the same validation as admin-authored content.

## 6. Extension rules

### Add content item
Author/import → validate → preview → publish → assign to curriculum. No code for supported types.

### Add exercise type
Add versioned contracts, backend implementation, renderer, evidence mapping, editor preview, accessibility behavior, analytics, tests, and documentation.

### Add provider
Implement port, conformance tests, configuration, health/cost mapping, retry classification, privacy review, and fallback behavior. Domain code remains unchanged.

### Add course/language
Compose catalog/objectives/releases; add linguistic plugin only for genuinely language-specific behavior. Do not fork the application.

## 7. API evolution

Prefer additive compatible changes. Version breaking contracts. Regenerate clients in the same PR. Errors have stable codes. Idempotency is mandatory for retried writes. Deprecation has a measured removal plan.

## 8. Database evolution

One owning module per migration. Use expand/migrate/contract. Do not edit applied migrations. Backfills are resumable. Constraints follow cleaned data. Destructive operations require explicit review, backup evidence, and recovery plan.

## 9. Async work

Jobs are versioned, idempotent, observable, timeout-bounded, retry-classified, and dead-lettered. Do not pass secrets or huge payloads through Redis; pass secure references. Persist valuable state before enqueueing.

## 10. Error handling

Use typed domain/application errors and stable API codes. Unexpected exceptions are logged with correlation ID and sanitized response. Never swallow failures, expose secrets, or tell the learner work is saved when it is not.

## 11. Observability

New critical flows define logs, metrics, and failure visibility. Logs are structured. Provider calls record cost/latency. Learning analytics and operational telemetry are separated.

## 12. Testing

A behavior change includes tests at the cheapest effective layer. Bug fixes begin with a failing regression test. External providers use fakes/contracts in CI. Time/randomness/IDs are injectable where determinism matters.

## 13. UX and accessibility

Mobile-first, keyboard-operable, semantic, localization-safe, and tolerant of latency. Loading, empty, partial, error, retry, and offline states are designed with the happy path.

## 14. Security and privacy

Validate every boundary, authorize every resource, redact logs, minimize data, respect consent/retention, and treat content/provider output as untrusted. Any change involving voice, biography, imports, or sharing receives explicit privacy review.

## 15. Pull request checklist

- outcome and scope stated;
- acceptance criteria demonstrated;
- domain/module ownership respected;
- contract/schema changes documented;
- migrations safe;
- tests pass;
- accessibility checked;
- security/privacy reviewed;
- observability added;
- docs/ADR updated;
- deployment and rollback understood;
- screenshots or API examples included where useful.

## 16. Definition of architectural debt

A shortcut is architectural debt when it binds content to code, UI to persistence, domain to a vendor, progress to mutable ordering, published meaning to in-place edits, or async correctness to best-effort delivery. Such debt must be named, scoped, owned, and scheduled.
