# DeutschDeploy21 documentation

This directory is the authoritative design baseline for the product. It explains what will be built, why boundaries exist, and what must remain extensible.

## Recommended reading order

1. [Product vision](01-product-vision.md)
2. [Product requirements](02-product-requirements.md)
3. [System architecture](03-system-architecture.md)
4. [Domain and data model](04-domain-data-model.md)
5. [Content architecture](05-content-architecture.md)
6. [Curriculum](06-curriculum.md)
7. [Exercise engine](07-exercise-engine.md)
8. [Progress and review](08-progress-and-review.md)
9. [AI, speech, and interviews](09-ai-speech-interview.md)
10. [Platform and Railway](10-platform-railway.md)
11. [Security and privacy](11-security-privacy.md)
12. [Testing and quality](12-testing-quality.md)
13. [Roadmap](13-roadmap.md)
14. [Development rules](14-development-rules.md)
15. [Glossary](15-glossary.md)
16. [UX and information architecture](16-ux-information-architecture.md)
17. [Phase 1 platform skeleton](17-phase-1-platform-skeleton.md)
18. [Phase 2 content and publishing](18-phase-2-content-publishing.md)
19. [Phase 3 deterministic learning loop](19-phase-3-learning-loop.md)
20. [Phase 4 mastery and spaced review](20-phase-4-mastery-review.md)
21. [Phase 5A silent multi-exercise engine](21-phase-5a-silent-exercise-engine.md)
22. [Phase 5B exercise explosion](22-phase-5b-exercise-explosion.md)
23. [Phase 5C interview drills](23-phase-5c-interview-drills.md)
24. [Phase 5D full 21-day curriculum](24-phase-5d-full-curriculum.md)
25. [Phase 6 durable speech pipeline](25-phase-6-speech-pipeline.md)
26. [Phase 7 mock interview and readiness](26-phase-7-mock-interview-readiness.md)
27. [Phase 8A motivation, mobile polish and accessibility foundation](27-phase-8a-motivation-mobile-accessibility.md)
28. [Architecture Decision Records](adr/README.md)

## Document authority

When implementation and documentation disagree:

1. determine the latest intentional decision;
2. record architectural or irreversible choices in an ADR;
3. update implementation and documents in the same pull request;
4. never preserve accidental behavior merely because it exists.

## Status labels

- **Proposed:** under discussion.
- **Accepted:** approved implementation baseline.
- **Superseded:** replaced by another decision.
- **Deprecated:** present but scheduled for removal.

## Change checklist

A feature proposal identifies user outcome, affected domain concepts, content/curriculum impact, API/schema changes, background work, failure modes, privacy/retention, analytics, migration/rollback, tests, and Railway resource impact.
