# ADR-0006: Release-pinned curriculum and append-only attempts

**Status:** Accepted

## Context

Course content will improve over time. Learner progress must not change retroactively when items reorder, accepted answers change, or evaluation models update.

## Decision

Enrollments pin an immutable course release. Activity instances snapshot exact learner-facing material. Attempts are append-only. Evaluations are versioned and may supersede one another without rewriting the answer. Derived mastery is rebuildable from evidence/events.

## Consequences

Corrections and migrations need explicit policy. Storage grows with history. Debugging, comparison, algorithm evolution, and auditability become substantially safer.

## Rejected

- Enrollment always follows latest draft.
- Progress stored as completed day numbers.
- Retry overwrites the previous answer.
- Re-evaluation overwrites the original score without provenance.

## Reconsider when

Retention/privacy requirements require deletion or anonymization. Such workflows preserve referential and aggregate integrity while honoring policy.
