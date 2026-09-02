# DeutschDeploy21

> **Speak German. Explain Your Work. Get Hired.**

DeutschDeploy21 is a focused, mobile-first learning platform for software professionals preparing for German job interviews. It combines a structured 21-day curriculum, active recall, spaced repetition, silent practice, interview-transfer drills, speaking practice, and realistic HR and technical mock interviews.

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
- **Media:** private S3-compatible object storage behind an adapter; filesystem only for development/test and Railway Bucket-compatible storage for staging/production
- **Deployment:** Docker services on Railway
- **AI and speech:** provider-neutral gateways; speech-to-text is wired while richer AI evaluation remains optional and replaceable

The implementation is a modular monolith with separate web, API, and worker processes. Microservices are not required until operational evidence justifies them.

## Repository

```text
apps/
  api/                 FastAPI application, migrations, worker
  web/                 Next.js mobile-first PWA
content/                version-controlled source content and curriculum manifests
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
**Phase 5A — Silent multi-exercise engine: merged and CI verified.**  
**Phase 5B — Exercise explosion: merged and CI verified.**  
**Phase 5C — Interview drills: merged and CI verified.**  
**Phase 5D — Full 21-day curriculum: merged and CI verified.**  
**Phase 6 — Durable speech pipeline: merged and CI verified; production Railway provisioning remains an environment step.**  
**Phase 7 — Mock interview and readiness: implemented and CI verified on PR #10; merge pending.**

The executable platform includes private authentication, PostgreSQL migrations, Redis-assisted durable jobs, a worker, health checks, same-origin web→API routing, PWA shell, OpenAPI-generated TypeScript contracts, Docker Compose, Railway configuration, and CI.

The content layer adds relational drafts, immutable published versions, typed verb grammar, localizations, examples, dry-run/idempotent imports, publication history, and a controlled 100-verb software-interview catalog.

`/learn` consumes an immutable, version-controlled curriculum manifest. CourseRelease v2 contains 21 days and 133 required activities: the complete 100-verb foundation, all ten deterministic content exercise families, and structured interview-transfer drills. Days 1–15 introduce all 100 starter verbs exactly once; later days emphasize role depth, behavioral structure, architecture reasoning, recovery and deterministic final validation.

Existing three-day CourseRelease v1 remains immutable. New learners start v2. Existing v1 learners receive an explicit upgrade path instead of silent repinning. Compatible historical course work carries only when the exact pinned content version and exercise type match; original attempts, evaluations and mastery history are never copied or rewritten.

Every submitted learning, practice, interview-drill, or review attempt produces idempotent mastery evidence. `learning_targets`, append-only `mastery_events`, rebuildable `learner_mastery`, and `review_queue_entries` keep completion separate from memory reliability.

`/practice` is a first-class Silent Mode for crowded buses, trains, offices and other places where speaking is impractical. Ten deterministic exercise families share one attempt/evaluation/mastery pipeline: meaning choice, German typing recall, Partizip II choice, `haben`/`sein` choice, sentence ordering, German↔Persian matching, interview-example cloze, usage error spotting, typed Perfekt production, and phrase building.

`/drills` is the Interview Lab. It provides 18 curated deterministic drills across six interview skills: best-answer quality, HR structure, STAR behavioral structure, technical explanation, architecture sequencing, and recovery-phrase recall under visible time pressure. The same drills can also appear as required late-course activities without optional Interview Lab sessions satisfying course progress.

`/speak` is the durable Speak Mode. Recording is consent-gated and optional. A speech attempt and frozen prompt are persisted before provider analysis; private audio is uploaded with size/type/duration bounds, transcription runs through the durable worker queue, the raw provider transcript remains immutable, learner corrections are append-only, and text-level feedback is versioned. Failed transcription can be retried without losing the attempt, manual text fallback keeps the mode usable without microphone access, and raw audio can be deleted while derived transcript/feedback remain. Pronunciation and accent are intentionally not scored without credible assessment evidence.

`/mock` is the interview-transfer layer. Guided, Practice and Realistic sessions pin a version-controlled interview blueprint and materialize durable turns. Weak answers can create one deterministic contextual follow-up, text submissions are idempotent, voice answers reuse the exact Phase 6 `SpeechAttempt` pipeline, and completion creates a readiness report separate from vocabulary mastery. Baseline and final reports can be compared only under compatible blueprint/rubric boundaries.

ReleaseActivity can reference either an exact content version or a version-controlled interview drill source. The runtime keeps source identity, course placement, immutable learner-facing instances and mastery targets separate.

See [`docs/17-phase-1-platform-skeleton.md`](docs/17-phase-1-platform-skeleton.md), [`docs/18-phase-2-content-publishing.md`](docs/18-phase-2-content-publishing.md), [`docs/19-phase-3-learning-loop.md`](docs/19-phase-3-learning-loop.md), [`docs/20-phase-4-mastery-review.md`](docs/20-phase-4-mastery-review.md), [`docs/21-phase-5a-silent-exercise-engine.md`](docs/21-phase-5a-silent-exercise-engine.md), [`docs/22-phase-5b-exercise-explosion.md`](docs/22-phase-5b-exercise-explosion.md), [`docs/23-phase-5c-interview-drills.md`](docs/23-phase-5c-interview-drills.md), [`docs/24-phase-5d-full-curriculum.md`](docs/24-phase-5d-full-curriculum.md), [`docs/25-phase-6-speech-pipeline.md`](docs/25-phase-6-speech-pipeline.md), and [`docs/26-phase-7-mock-interview-readiness.md`](docs/26-phase-7-mock-interview-readiness.md).

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

Install the starter content catalog after migration with either the private `/catalog` screen or:

```bash
cd apps/api
uv run python -m app.scripts.seed_content
```

After signing in:

- open `/learn` for the complete 21-day structured course;
- open `/practice` for unlimited ten-mode Silent Practice;
- open `/drills` for silent-first interview-transfer drills;
- open `/speak` for consent-gated recording, transcription, correction and speaking feedback;
- open `/mock` for guided, practice or realistic interview sessions and readiness reports;
- open `/review` for due spaced-review work and the combined mastery map.

## End-to-end proof paths

Platform:

```text
Browser → Next.js → FastAPI → PostgreSQL → Redis → worker → PostgreSQL → Browser
```

Content:

```text
CSV/JSON → validate → dry-run → draft → publish → immutable version → API → catalog
```

Curriculum publication:

```text
Version-controlled manifest → validate coverage/workload → checksum
→ immutable CourseRelease → pinned content/drill sources → enrollment
```

Learning:

```text
Pinned release activity → immutable activity instance → idempotent attempt
→ deterministic evaluation → curriculum progress + mastery evidence → review schedule
```

Release upgrade:

```text
v1 enrollment + historical course attempts → explicit upgrade
→ new v2 enrollment → exact compatible completion carry-over
→ original attempts/history unchanged
```

Silent practice:

```text
Pinned release content → registered exercise variant → tap/type/match/order answer
→ deterministic evaluation → skill-specific mastery evidence → review schedule
```

Interview drills:

```text
Version-controlled drill blueprint → immutable interview activity instance
→ choice/type/order answer → deterministic evaluation → interview-skill mastery → review
```

Speech:

```text
Browser MediaRecorder → private media adapter → durable SpeechAttempt + PlatformJob
→ Redis signal → worker → provider-neutral transcription → immutable raw transcript
→ learner correction → versioned text-level feedback → retry/new rep
```

Mock interview:

```text
Versioned interview blueprint → frozen session plan → durable turn
→ text or linked SpeechAttempt → deterministic rubric → contextual follow-up
→ completed readiness report → compatible baseline/final comparison
```

Mastery and review:

```text
Attempt → evaluation → stable learning target → mastery event → rebuildable projection
→ explainable review queue → frozen exercise review → new evidence → reschedule
```

## Non-negotiable principles

1. Learning content is data, never hard-coded page logic.
2. Curriculum placement is separate from reusable content.
3. Exercise rendering, generation, and evaluation are separate.
4. Published content and curriculum releases are immutable; edits never silently invalidate history.
5. Progress references immutable learning targets and compatible evidence, not screen positions.
6. AI may propose or evaluate, but canonical content remains reviewable.
7. External providers are replaceable through ports and adapters.
8. Railway is the deployment target, not a domain dependency.
9. Accessibility, mobile usability, observability, testing, and safe migrations are release requirements.
10. Private-user scope may simplify features but never corrupt the long-term data model.

## Documentation

The [`docs/README.md`](docs/README.md) index contains the complete product and engineering baseline. Architecture-impacting changes must update the relevant document or add an ADR.
