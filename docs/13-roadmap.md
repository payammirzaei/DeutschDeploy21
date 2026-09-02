# Roadmap and delivery plan

**Status:** Proposed execution baseline

## 1. Delivery principle

Design for the target product, activate capability in evidence-driven increments. Every phase produces a usable vertical slice or a verified foundation. Percent complete is measured against acceptance criteria, not files created.

## Phase 0 — Foundation

### Deliverables
- vision, requirements, architecture, domain model;
- content/curriculum/exercise contracts;
- security, testing, Railway, and development rules;
- ADRs;
- initial UX information architecture and design tokens;
- repository scaffold decision;
- prioritized backlog.

### Exit criteria
Documents have no known contradictions, unresolved high-impact choices are listed, MVP boundary is accepted, and first vertical slice can be implemented without inventing foundational concepts.

## Phase 1 — Platform skeleton

### Deliverables
- monorepo/workspace;
- Next.js web, FastAPI API, worker;
- local Docker environment;
- PostgreSQL/Redis migrations/connectivity;
- configuration validation;
- private authentication;
- health endpoints;
- generated API client;
- CI baseline;
- Railway staging topology.

### Exit criteria
One provisioned user signs in; web calls API; API commits to PostgreSQL; worker processes an idempotent test job; deployment and health checks succeed.

## Phase 2 — Content and publishing

### Deliverables
- content/catalog schema;
- verb and example editor;
- localization and tags;
- draft validation;
- CSV/JSON dry-run import;
- version diff;
- publish/release manifest;
- initial verified 100-verb dataset.

### Exit criteria
A new verb is added, previewed, published, related to examples, and available to curriculum without code modification. Historical published version remains intact after correction.

## Phase 3 — Curriculum and deterministic learning

### Deliverables
- course/track/module/lesson/objective;
- release-pinned enrollment;
- daily plan;
- initial exercise registry;
- attempt/evaluation persistence;
- text feedback;
- responsive PWA shell;
- Days 1–3 complete.

### Exit criteria
Learner completes and resumes a day across devices. Duplicate submission is harmless. Course reorder does not corrupt progress.

## Phase 4 — Mastery and review

### Deliverables
- granular learning targets;
- mastery events/projection;
- scheduler;
- due-review session;
- workload replanning;
- baseline dashboard;
- explanation codes.

### Exit criteria
Wrong/hinted/correct attempts create different schedules; projection rebuild matches current state; missed days produce a manageable plan.

## Phase 5 — Complete 21-day content

### Deliverables
- all modules/days;
- question taxonomy;
- verified personalized examples;
- baseline/final assessment;
- guided answer builder;
- recovery phrases;
- content coverage report.

### Exit criteria
Every day passes workload, content, rendering, and evaluator compatibility checks. No required answer relies on fabricated experience.

## Phase 6 — Speech pipeline

### Deliverables
- consent;
- signed upload/finalization;
- worker transcription;
- transcript correction;
- speech/language feedback;
- retry/dead-letter handling;
- media retention/deletion.

### Exit criteria
Recording survives normal network retry, processing failure is recoverable, provider outage does not block text work, and deletion removes storage object as promised.

## Phase 7 — Mock interview and readiness

### Deliverables
- interview blueprints/modes;
- turn state;
- deterministic and AI follow-ups;
- rubric evaluation;
- reports;
- baseline/final comparison;
- readiness dimensions/confidence.

### Exit criteria
Learner completes guided and realistic interviews. Reports cite evidence, preserve truthfulness, and remain comparable under pinned rubric versions.

## Phase 8 — Motivation and polish

### Deliverables
- XP/streak/badges;
- refined mobile UX;
- accessibility audit;
- offline-safe text attempts;
- performance optimization;
- notifications only if requested;
- production observability/cost dashboard.

### Exit criteria
Critical accessibility journeys pass; poor connection does not duplicate attempts; gamification cannot block practice; operational alerts are actionable.

## Phase 9 — Public-product readiness (inactive until chosen)

Public registration, account recovery, onboarding, CV import, multi-track selection, billing, legal pages, support workflows, abuse prevention, expanded privacy controls, and production scaling.

## 2. MVP boundary

The meaningful personal MVP includes Phases 0–4 and enough Day 1–2 content to validate the loop. A learning-complete private product includes through Phase 7. Phase 9 is explicitly not required for personal use.

## 3. Prioritization

Use risk-first vertical slices:

1. content versioning and adding a verb;
2. one deterministic exercise through progress;
3. release pinning;
4. review scheduling;
5. one speech attempt end-to-end;
6. one mock interview end-to-end;
7. breadth of content and polish.

## 4. Backlog item template

Every item states user outcome, scope/non-scope, acceptance criteria, domain impact, schema/API changes, failure states, security/privacy, analytics, tests, migration/rollback, and dependencies.

## 5. Release strategy

Use small releases, migration compatibility, staging smoke tests, feature activation configuration, and visible release notes. Do not merge incomplete hidden architecture that lacks an active use case unless it is a necessary seam for the immediate next phase.

## 6. Risks

- content creation exceeds coding effort;
- AI feedback seems authoritative but is inconsistent;
- voice cost/latency harms flow;
- over-engineering delays the first learning loop;
- under-modeling versions corrupts history;
- motivational UI hides weak pedagogy;
- personalized content fabricates facts;
- public scope distracts from personal outcome.

Each phase must update risk ownership and mitigation evidence.
