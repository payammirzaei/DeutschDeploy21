# Phase 8B — Offline-safe attempts and operational visibility

**Status:** Implemented, CI verification pending

## Outcome

Phase 8B protects deterministic text practice against transient connectivity loss and exposes the runtime signals required to operate the API/Redis/worker/provider path without guessing.

## Offline-safe learning attempts

Eligible graded text attempts now pass through a browser outbox before they can be lost to a network interruption.

The outbox:

- stores pending requests in IndexedDB on the learner's device;
- keys pending work by activity-instance URL so repeated taps cannot create multiple queued copies for the same activity;
- preserves the original `Idempotency-Key` during every replay;
- replays requests in creation order when connectivity returns;
- removes an item only after the server returns a successful JSON response;
- stops replay on authentication loss or a network failure;
- never marks progress complete locally before the server accepts the evidence.

The global application shell mounts one synchronizer. It flushes the outbox on application startup and browser `online` events, and displays an accessible status banner while pending attempts remain.

The 21-day learning path, Silent Practice, Interview Lab and Spaced Review all use the same safe submission path. If an answer is queued while the current page remains open, the server result is delivered back to that page after synchronization so normal feedback can continue.

This is deliberately narrower than a fully offline curriculum. Prompts are not fabricated or advanced locally when the server cannot authorize the next activity. The guarantee is that an answer already produced by the learner is not lost or duplicated because the connection dropped during submission.

## Operational summary

`GET /api/v1/platform/operations` is authenticated and combines durable database state, Redis queue state and provider invocation accounting.

It exposes:

- queued and running jobs;
- succeeded and failed worker jobs in the last 24 hours;
- age of the oldest queued job;
- Redis queue depth;
- provider invocation and failure counts in the last 24 hours;
- recorded provider estimated cost in micro-USD for the last 24 hours;
- explicit alert codes.

Initial actionable alert rules are:

- `redis_queue_unavailable` when queue depth cannot be inspected;
- `redis_queue_backlog` when Redis depth exceeds 20 signals;
- `worker_queue_stale` when the oldest queued DB job is older than 120 seconds;
- `worker_failures_24h` when any worker job failed in the last 24 hours;
- `provider_failures_24h` when any recorded provider call failed in the last 24 hours.

The dashboard folds these signals into the top-level system status and shows the 24-hour provider cost estimate next to the existing end-to-end worker smoke test.

## Safety properties

- Server-side idempotency remains the authority for deduplication.
- The browser never invents a successful evaluation while offline.
- A queued answer cannot unlock, complete or modify mastery until replay succeeds.
- Redis telemetry failure degrades operational visibility instead of crashing the endpoint.
- Cost display uses already-recorded provider invocation estimates; it does not estimate untracked spend.

## Remaining Phase 8 work

- full keyboard/screen-reader/contrast audit across critical journeys;
- performance and bundle review;
- Railway staging smoke test under production-like environment variables;
- final product polish and Phase 8 exit checklist.
