# DeutschDeploy21 documentation

This directory is the authoritative design baseline for the product. It explains not only what will be built, but why boundaries exist and what must remain extensible.

## Recommended reading order

1. [Product vision](01-product-vision.md) — purpose, users, outcomes, and boundaries.
2. [Product requirements](02-product-requirements.md) — functional and non-functional requirements.
3. [System architecture](03-system-architecture.md) — components, modules, flows, and evolution.
4. [Domain and data model](04-domain-data-model.md) — stable concepts and persistence rules.
5. [Content architecture](05-content-architecture.md) — authoring, versioning, tagging, import, and publishing.
6. [Curriculum](06-curriculum.md) — the 21-day learning design and adaptation.
7. [Exercise engine](07-exercise-engine.md) — extensible activity types and evaluation.
8. [Progress and review](08-progress-and-review.md) — mastery, attempts, scheduling, and readiness.
9. [AI, speech, and interviews](09-ai-speech-interview.md) — provider-neutral AI workflows.
10. [Platform and Railway](10-platform-railway.md) — deployable services and operations.
11. [Security and privacy](11-security-privacy.md) — threat boundaries and data handling.
12. [Testing and quality](12-testing-quality.md) — verification strategy.
13. [Roadmap](13-roadmap.md) — phased delivery and exit criteria.
14. [Development rules](14-development-rules.md) — conventions and change discipline.
15. [Glossary](15-glossary.md) — shared language.

## Document authority

When implementation and documentation disagree:

1. Confirm whether the implementation or document reflects the latest intentional decision.
2. Record the decision in an ADR when it affects architecture or irreversible cost.
3. Update both the implementation and affected documents in the same pull request.
4. Never preserve an accidental behavior merely because it already exists.

## Status labels

Each future ADR and major specification should use one of:

- **Proposed:** under discussion;
- **Accepted:** approved for implementation;
- **Superseded:** replaced by another decision;
- **Deprecated:** still present but scheduled for removal.

## Change checklist

A feature proposal must identify:

- user outcome;
- affected domain concepts;
- content and curriculum impact;
- API and schema changes;
- background work;
- failure modes;
- privacy and retention impact;
- analytics events;
- migration and rollback plan;
- test coverage;
- Railway resource impact.
