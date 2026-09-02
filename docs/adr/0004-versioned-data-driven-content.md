# ADR-0004: Versioned data-driven content

**Status:** Accepted

## Context

The product must add verbs, questions, examples, and courses without code changes while preserving what historical learners actually saw.

## Decision

Represent supported content types as validated data with stable logical IDs and immutable published versions. Curriculum relates to exact versions through release manifests. Drafts are mutable; published meaning changes only by new version.

## Consequences

Adding content becomes editorial. Historical attempts remain interpretable. Authoring, validation, preview, release, migration, and archival require explicit product features.

## Rejected

- Hard-coded lesson components.
- One mutable row per verb referenced by all history.
- Unvalidated arbitrary JSON as the entire domain model.
- Copying content into each day/course.

## Reconsider when

Never for the core principle. Storage representation may evolve through a superseding ADR while retaining immutable published meaning.
