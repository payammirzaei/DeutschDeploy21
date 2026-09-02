# Phase 3 — Deterministic learning loop

**Status:** Implemented and CI verified  
**Branch:** `feat/phase-3-learning-loop`  
**Primary learner UI:** `/learn`

## 1. Outcome

Phase 3 turns the versioned Phase 2 content catalog into the first real learning product flow.

The learner can initialize a pinned course release, open Days 1–3, receive deterministic activities, submit answers, receive immediate feedback, continue after either correct or incorrect responses, leave the application, and resume from durable PostgreSQL state.

The core proof path is:

```text
Published content version
  → immutable course release
  → learner enrollment
  → deterministic activity instance
  → append-only attempt
  → deterministic evaluation
  → progress/resume
```

## 2. Database and domain runtime

Migration `20260902_0003_learning_loop.py` adds the first executable curriculum and learning-runtime schema:

- `courses`
- `course_releases`
- `course_days`
- `release_activities`
- `enrollments`
- `activity_instances`
- `attempts`
- `evaluations`

The schema preserves the architecture baseline that identity, published meaning, curriculum placement, runtime instances, attempts, and evaluations are separate concepts.

## 3. Release pinning

A course release is immutable learner-facing structure.

Each `release_activity` references one exact `content_version_id`. Enrollment references one exact `course_release_id`. An activity instance therefore does not ask for the latest verb version at render time; it materializes from the version pinned by the learner's release.

This prevents a later correction such as `entwickeln v2` from silently changing an activity that was originally assigned with `entwickeln v1`.

## 4. Starter course slice

The first release is:

**21-Day German Software Interview Sprint**  
Target: German A2–B1  
Implemented learner slice: Days 1–3

### Day 1 — Introduce yourself

Objective: build vocabulary for a clear 60-second professional introduction.

Seven verbs are pinned for introduction, work, learning, speaking, explanation, description, and questions.

### Day 2 — Explain what you build

Objective: describe software work, tools, and implementation responsibilities.

Seven verbs cover development, programming, implementation, building, creating, using, and applying tools.

### Day 3 — Problems and delivery

Objective: explain testing, debugging, problem solving, and improvement work.

Seven verbs cover testing, checking, analysis, solving, finding, fixing, and improving.

The slice therefore contains **21 pinned activities**.

## 5. Initial exercise type

The first registered runtime interaction is:

`meaning_multiple_choice` — contract version 1

Materialization is deterministic from the pinned content and release activity. Each instance stores:

- exact content version;
- exercise type and contract version;
- learner-facing prompt snapshot;
- four choices;
- answer key;
- prompt checksum;
- creation timestamp.

Persian translations are currently used as the answer space because the private first release is configured for the current learner. This is a configuration choice, not a long-term schema assumption.

## 6. Deterministic choices

The correct answer comes from the pinned verb localization. Distractors are selected only from distinct Persian translations already pinned into the same release.

Choice ordering and IDs use stable hashes so the same source state creates reproducible materialization rather than relying on untracked random behavior.

## 7. Attempts and evaluation

Attempt submission requires an `Idempotency-Key`.

A submitted attempt stores:

- learner and enrollment;
- exact activity instance;
- raw answer;
- normalized answer;
- optional client duration;
- submission timestamp;
- idempotency key.

The attempt is append-only. Retrying later creates new evidence instead of rewriting the old answer.

The first evaluator is deterministic, version 1. It currently returns a score of 100 for the correct choice or 0 otherwise and stores a machine-readable feedback code.

## 8. Wrong answers do not block progression

Phase 3 intentionally does **not** implement retry-until-correct gating.

Once an activity is submitted, it counts as submitted for day progression whether the answer was correct or incorrect. Incorrect responses remain durable evidence. Phase 4 will convert that evidence into mastery state and targeted spaced review.

This keeps the daily learning flow moving while preserving enough history to revisit weak targets intelligently.

## 9. Resume behavior

`GET /api/v1/learning/home` reconstructs learner-visible progress from durable runtime state.

The learner sees:

- current course and release version;
- current day;
- Days 1–3;
- submitted and total activity counts;
- completed status per day.

`POST /api/v1/learning/days/{day_number}/next` returns the next unsubmitted activity, reusing an already materialized instance when one exists.

## 10. API surface

Authenticated Phase 3 endpoints:

```text
POST /api/v1/learning/start
GET  /api/v1/learning/home
GET  /api/v1/learning/days/{day_number}
POST /api/v1/learning/days/{day_number}/next
POST /api/v1/learning/instances/{instance_id}/attempts
```

The attempt endpoint requires an `Idempotency-Key` header.

## 11. Learner UI

The `/learn` PWA route provides the first complete learner workspace.

It includes:

- first-run learning initialization;
- overall foundation progress;
- Day 1–3 navigation;
- day objectives and counts;
- four-choice activity rendering;
- answer duration tracking;
- durable submission feedback;
- correct/review-needed states;
- next-activity and next-day continuation;
- resume from server state;
- responsive mobile layout;
- reduced-motion behavior.

The dashboard now makes the learning loop the primary product action while retaining access to the content catalog and platform smoke check.

## 12. Verified invariants

Integration tests verify that:

1. starting the course creates or reuses a release with exactly 21 pinned activities;
2. the learner home contains three days with seven activities each;
3. an activity instance references the same exact content version pinned by the course release;
4. each first exercise contains four choices;
5. resubmitting the same request with the same idempotency key returns the same attempt and evaluation;
6. a submitted activity is not returned again as the next activity;
7. completing all required Day 1 submissions advances the enrollment to Day 2;
8. progression depends on submission, not only on correct answers.

## 13. CI proof

The final Phase 3 head passed the complete repository CI pipeline:

- PostgreSQL and Redis service startup;
- Alembic migrations 0001, 0002, and 0003;
- Ruff;
- backend unit/integration tests;
- OpenAPI export;
- OpenAPI-to-TypeScript client generation;
- frontend ESLint;
- TypeScript type checking;
- Next.js production build.

## 14. Intentional limits

Phase 3 is a vertical slice, not the final curriculum engine.

Still intentionally deferred:

- additional exercise renderers such as cloze, conjugation, ordering, translation, and speaking;
- complete Days 4–21 curriculum;
- granular learning targets;
- mastery projection;
- spaced-review scheduler and due queue;
- hints and hint evidence weighting;
- offline attempt queue;
- richer release authoring and migration simulation;
- speech and interview runtime.

These are deferred without weakening the identity/version/runtime contracts already implemented.

## 15. Next phase

Phase 4 adds the mastery and review engine on top of Phase 3 evidence:

```text
Attempt + Evaluation
  → mastery event
  → learner mastery projection
  → next-review calculation
  → due review queue
  → targeted review session
```

The key requirement is explainability: the system must be able to say why a target is due and rebuild learner mastery from durable evidence/events rather than relying on an opaque mutable score.
