# Phase 4 — Mastery and spaced review

**Status:** Implemented on feature branch; merge requires green CI.

## Outcome

Phase 4 separates workflow completion from memory reliability. Every deterministic learning or review attempt becomes append-only mastery evidence. A versioned scheduling policy projects current mastery and maintains an explainable review queue.

## Runtime path

```text
Attempt
  → Evaluation
  → LearningTarget
  → MasteryEvent (append-only)
  → LearnerMastery projection
  → ReviewQueueEntry
  → /review
  → review attempt against frozen ActivityInstance
  → new MasteryEvent
  → reschedule
```

## Persistence

Migration `20260902_0004` adds:

- `learning_targets`
- `mastery_events`
- `learner_mastery`
- `review_queue_entries`

A learning target is currently the exact published content version plus `meaning_recognition` and `recognition` mode. Later exercise types can add production, grammar, speaking and interview-transfer targets without changing the projection model.

## Evidence invariants

- one submitted attempt creates at most one mastery event;
- duplicate idempotency-key submissions do not duplicate evidence;
- mastery events are durable history;
- `learner_mastery` is a rebuildable projection;
- review queue entries store scheduler version and explanation code;
- historical review reuses the exact frozen ActivityInstance and content version;
- a newer content publication cannot silently rewrite historical evidence.

## Scheduler v1

The first policy is intentionally interpretable and isolated behind the mastery service boundary. It is SM-2-inspired rather than claiming full SM-2 or FSRS compatibility.

Current state progression for recognition evidence:

- incorrect → `review`, short interval, high priority, lapse increment;
- first success → `learning`, 1-day interval;
- second consecutive success → `review`, 3-day interval;
- third/fourth consecutive success → `stable`, 7-day interval;
- fifth+ consecutive success → `mastered`, 21-day maintenance interval.

Every projection stores stability, difficulty, confidence, streak, lapses, evidence count, due time, scheduler version and an explanation code.

The policy is replaceable. A future FSRS implementation can coexist behind a new scheduler version and migration/replay policy.

## Review queue

`GET /api/v1/review/home` returns:

- due count;
- scheduled count;
- weak-target count;
- mastered count;
- next due time;
- explainable queue items;
- current mastery map.

`POST /api/v1/review/next` returns the highest-priority due target. It reuses the exact frozen prompt and choices stored on the original activity instance.

Review submission uses the existing idempotent learning-attempt endpoint, so retries and reviews share one durable attempt/evaluation path.

## Rebuildability

`POST /api/v1/review/rebuild` deletes only user-specific mastery projections/events/queue rows and replays durable attempts plus evaluations in chronological order. Learning targets remain stable identities.

CI integration tests compare projection state before and after rebuild. This makes projection corruption recoverable and provides a foundation for later scheduler migrations.

## Web experience

`/review` is mobile-first and shows:

- due-now count;
- weak and mastered counts;
- why the current item is due;
- frozen review question and choices;
- correctness feedback;
- mastery state and evidence confidence;
- an empty-queue state with next scheduled review.

The dashboard surfaces the live review summary and makes due review the primary action when relevant.

## Deliberately deferred

Phase 4 does not yet implement:

- FSRS parameter fitting;
- multiple target dimensions from one attempt;
- hint-weighted evidence;
- speaking-production evidence;
- workload/time-budget replanning across missed curriculum days;
- offline review queue mutation;
- prerequisite graph prioritization;
- notification delivery.

Those additions build on the same event/projection/scheduler boundary rather than replacing it.

## Phase exit evidence

The branch is ready to exit Phase 4 when CI proves:

1. migrations 0001–0004 succeed on PostgreSQL;
2. Ruff passes;
3. an attempt creates mastery evidence exactly once;
4. a future-due target becomes retrievable as a due review when clock time advances;
5. review reuses frozen prompt/content identity;
6. another review attempt updates streak/evidence and reschedules;
7. rebuilding from attempts reproduces the projection;
8. OpenAPI → TypeScript generation succeeds;
9. frontend lint, typecheck and production build succeed.
