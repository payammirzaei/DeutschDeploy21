# DeutschDeploy21

> **Speak German. Explain Your Work. Get Hired.**

DeutschDeploy21 is a focused, mobile-first learning platform for software professionals preparing for German job interviews. It combines a structured 21-day curriculum, active recall, spaced repetition, silent practice, speaking practice, and realistic HR and technical mock interviews.

The first release is personalized for one learner and the Software Developer track (German A2–B1), while the domain model is designed to later support multiple users, professions, languages, course lengths, and AI or speech providers without rewriting the learning core.

## Product outcome

After 21 days, the learner should be able to:

- introduce themselves naturally in German;
- explain experience, responsibilities, projects, architecture, and technical decisions;
- narrate problems and solutions with appropriate language;
- answer essential HR, behavioral, backend, frontend, DevOps, cloud, AI, and computer-vision questions;
- recover when a question is unclear;
- complete a realistic German interview and understand remaining weaknesses.

DeutschDeploy21 does **not** attempt to teach all German. It optimizes for a concrete performance outcome: a credible, understandable, job-relevant interview.

## Architecture

- **Web/PWA:** Next.js 16 + TypeScript
- **API:** FastAPI
- **Database:** PostgreSQL
- **Queue/cache:** Redis
- **Async work:** separate background worker with durable PostgreSQL job state
- **Media:** S3-compatible object storage behind an adapter (Phase 6)
- **Deployment:** Docker services on Railway
- **AI and speech:** provider-neutral gateways (later phases)

The implementation is a modular monolith with separate web, API, and worker processes. Microservices are not required until operational evidence justifies them.

## Repository

```text
apps/
  api/                 FastAPI application, migrations, worker
  web/                 Next.js mobile-first PWA
content/                version-controlled source content for controlled imports
packages/
  api-contract/        generated OpenAPI contract
docs/                   product, architecture, ADRs, delivery notes
.github/workflows/      CI and generated-contract verification
```

## Current status

**Phase 1 — Platform skeleton: merged and CI verified.**  
**Phase 2 — Content and publishing: merged and CI verified.**  
**Phase 3 — Deterministic learning loop: merged and CI verified.**  
**Phase 4 — Mastery and spaced review: merged and CI verified.**  
**Phase 5A — Silent multi-exercise engine: implementation / CI verification.**

The executable platform includes private authentication, PostgreSQL migrations, Redis-assisted durable jobs, a worker, health checks, same-origin web→API routing, PWA shell, OpenAPI-generated TypeScript contracts, Docker Compose, Railway configuration, and CI.

The content layer adds relational drafts, immutable published versions, typed verb grammar, localizations, examples, dry-run/idempotent imports, publication history, and a controlled 100-verb software-interview catalog.

The learner-facing loop at `/learn` creates a version-pinned course release for Days 1–3, materializes 21 required activities, persists append-only attempts and evaluations, gives immediate feedback, advances after submissions rather than retry-until-correct gating, and resumes from durable learner state.

Every submitted learning, practice, or review attempt produces idempotent mastery evidence. `learning_targets`, append-only `mastery_events`, rebuildable `learner_mastery`, and `review_queue_entries` keep completion separate from memory reliability.

Phase 5A adds `/practice`, a first-class Silent Mode for crowded buses, trains, offices and other places where speaking is impractical. Five deterministic exercise types currently share one generic attempt/evaluation pipeline: meaning choice, German typing recall, Partizip II choice, `haben`/`sein` choice, and tap-to-build sentence ordering. Silent practice is isolated from required course completion while still updating skill-specific mastery and spaced review.

See [`docs/17-phase-1-platform-skeleton.md`](docs/17-phase-1-platform-skeleton.md), [`docs/18-phase-2-content-publishing.md`](docs/18-phase-2-content-publishing.md), [`docs/19-phase-3-learning-loop.md`](docs/19-phase-3-learning-loop.md), [`docs/20-phase-4-mastery-review.md`](docs/20-phase-4-mastery-review.md), and [`docs/21-phase-5a-silent-exercise-engine.md`](docs/21-phase-5a-silent-exercise-engine.md).

## Local development

Prerequisites: Docker + Compose, Node.js 22+, Python 3.13/3.14, and `uv`.

```bash
cp .env.example .env
# Replace APP_SECRET_KEY and the bootstrap password before using the app.
make bootstrap
make up
```

Then open `http://localhost:3000`. API docs are available at `http://localhost:8000/api/docs` outside production.

Useful commands:

```bash
make migrate
make api-dev
make worker-dev
make web-dev
make api-client
make check
```

Install the starter learning catalog after migration with either the private `/catalog` screen or:

```bash
cd apps/api
uv run python -m app.scripts.seed_content
```

After signing in:

- open `/learn` for the structured course;
- open `/practice` for unlimited Silent Mode drills;
- open `/review` for due spaced-review work and the mastery map.

## End-to-end proof paths

Platform:

```text
Browser → Next.js → FastAPI → PostgreSQL → Redis → worker → PostgreSQL → Browser
```

Content:

```text
CSV/JSON → validate → dry-run → draft → publish → immutable version → API → catalog
```

Learning:

```text
Published content version → course release → enrollment → course activity instance
→ idempotent attempt → deterministic evaluation → curriculum progress/resume
```

Silent practice:

```text
Pinned release content → keyed exercise variant → tap/type/order answer
→ deterministic evaluation → skill-specific mastery evidence → review schedule
```

Mastery and review:

```text
Attempt → evaluation → learning target → mastery event → rebuildable projection
→ explainable review queue → frozen exercise review → new evidence → reschedule
```

## Non-negotiable principles

1. Learning content is data, never hard-coded page logic.
2. Curriculum placement is separate from reusable content.
3. Exercise rendering, generation, and evaluation are separate.
4. Published content is versioned; edits never silently invalidate history.
5. Progress references immutable learning targets, not screen positions.
6. AI may propose or evaluate, but canonical content remains reviewable.
7. External providers are replaceable through ports and adapters.
8. Railway is the deployment target, not a domain dependency.
9. Accessibility, mobile usability, observability, testing, and safe migrations are release requirements.
10. Private-user scope may simplify features but never corrupt the long-term data model.

## Documentation

The [`docs/README.md`](docs/README.md) index contains the complete product and engineering baseline. Architecture-impacting changes must update the relevant document or add an ADR.
