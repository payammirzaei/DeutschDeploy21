# Progress, mastery, and spaced review

**Status:** Accepted baseline

## 1. Definitions

- **Completion:** required workflow was submitted.
- **Correctness:** one attempt met its evaluator’s criteria.
- **Mastery:** accumulated evidence indicates reliable independent performance.
- **Readiness:** ability to perform across interview capabilities under realistic conditions.

These are separate. A completed lesson may contain weak targets; one correct answer does not prove mastery.

## 2. Target granularity

Progress attaches to a learning target such as “produce entwickeln in Perfekt in a project sentence,” not to a mutable screen or day index.

A target declares content/objective versions, skill dimension, production mode, expected difficulty, and prerequisites.

## 3. Attempt evidence

Evidence weight considers correctness, partial score, response mode, scaffolding, hint use, latency, repeated guessing, evaluator confidence, task difficulty, recency, and interview transfer.

Recognition evidence cannot fully replace free spoken production evidence.

## 4. Mastery states

- New
- Encountered
- Learning
- Review
- Stable
- Mastered
- Lapsed
- Suspended

State transitions follow a versioned policy. `Mastered` means a configured reliability level, not permanent knowledge.

## 5. Scheduling algorithm

Begin with a proven interpretable algorithm such as an SM-2-inspired scheduler, but isolate it behind `ReviewSchedulingPolicy`. Store algorithm version and inputs so a future FSRS-style policy can coexist or migrate safely.

Inputs include grade, confidence, elapsed time, target type, mode, hints, stability, difficulty, and lapses. Outputs include due time, interval, stability, difficulty, and explanation code.

## 6. Review queue

Queue composition balances:

1. overdue high-value targets;
2. recent failures;
3. prerequisite weaknesses;
4. interview-critical capabilities;
5. variety across exercise modes;
6. available session time.

The learner can see why an item is due. Manual practice does not silently remove scheduled review unless it provides qualifying evidence.

## 7. Daily planning

The planner combines required curriculum activities, due review, deferred speaking, and optional weak-area practice. It respects a time budget and prevents new content from crowding out review.

If the learner misses days, the system replans workload; it does not dump all missed activities into one impossible session.

## 8. Readiness model

Initial dimensions:

- introduction;
- experience and responsibility;
- project explanation;
- technical reasoning;
- behavioral stories;
- German grammar;
- active interview vocabulary;
- comprehensibility/fluency;
- clarification and recovery;
- independent performance.

Each dimension records score range, evidence count, evidence quality, recency, and confidence. The UI explains weak evidence rather than showing false precision.

## 9. Baseline comparison

The final report compares matched rubric dimensions, not raw exercise totals. It shows observed change, evidence examples, remaining weaknesses, and uncertainty.

## 10. Event and projection design

Attempts and mastery events are durable history. Current mastery, streak, daily status, and dashboard are projections. Projection builders are idempotent and replayable from a checkpoint.

## 11. Gamification

XP is awarded from events with caps against farming. Streak follows timezone-aware daily completion. Badges use explicit versioned criteria. Gamification never changes evaluator correctness or locks core practice.

## 12. Edge cases

- Correct after hint: reduced evidence.
- Same item repeated immediately: lower independence evidence.
- Provider evaluation delayed: attempt remains complete but mastery is pending.
- AI result replaced: append evaluation and recompute projection.
- Content superseded: historical evidence remains attached; compatibility policy may transfer some mastery.
- Timezone change: streak recalculates through documented policy, never silently deletes history.
- Offline duplicate: idempotency prevents duplicate attempts.

## 13. Privacy

Analytics may use pseudonymous identifiers and aggregate dimensions. Raw answer content and voice are not required for ordinary engagement metrics. Learner can inspect and delete retained recordings according to policy.
