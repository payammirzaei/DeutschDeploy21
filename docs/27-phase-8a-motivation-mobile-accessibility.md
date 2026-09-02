# Phase 8A — Motivation, mobile polish and accessibility foundation

**Status:** Implemented, CI verification pending

## Outcome

Phase 8 starts by making progress visible without creating a second source of truth. XP, levels, streaks and badges are derived from durable mastery evidence that already exists. Gamification is presentation only: it cannot unlock, hide, reorder or block learning work.

## Evidence-backed engagement

`GET /api/v1/engagement/summary` derives a compact learner summary from `mastery_events` and `learner_mastery`.

The response includes:

- total XP and current level;
- percentage progress through the current level;
- current and longest practice streak;
- graded rep count and correctness rate;
- mastered target count;
- deterministic badge progress.

No gamification tables or migrations are introduced in this slice. Rebuilding mastery evidence therefore preserves the motivational view automatically.

### XP policy

Every graded mastery event earns a base 10 XP plus up to 5 score-weighted XP. Score input is bounded to 0–100 before XP conversion. XP rewards a completed evidence-producing rep while still reflecting answer quality.

Levels are intentionally simple in v1: 250 XP per level. The policy is display-only and may be versioned later without changing learning history.

### Streak policy

The first personalized release uses `Europe/Berlin` calendar days. A streak remains alive through the current day when the most recent activity was yesterday, so the learner does not lose the displayed streak at midnight before having a chance to practice.

For a future multi-user release, timezone becomes a user preference rather than a product constant.

### Badge policy

Initial badges are deterministic milestones for:

- first graded rep;
- 25 graded reps;
- 100 graded reps;
- 3-day streak;
- 7-day streak;
- 10 mastered targets.

Locked badges expose progress. Earned badges are recomputable and never persisted as authority.

## Dashboard polish

The dashboard now starts with a compact momentum panel showing level, XP, streak, reps, accuracy, mastery and badge progress. Phase 7 is marked complete and Phase 8 is the active delivery phase.

Mobile refinements include:

- denser responsive metric layout;
- single-column badge cards on narrow phones;
- smaller mobile heading/lead sizing;
- reduced card spacing on narrow screens;
- minimum 44px primary interactive targets.

## Accessibility foundation

This slice adds a global `:focus-visible` treatment for links, buttons, inputs, textareas and selects. The level meter uses a native `progress` element with an accessible label, achievement state is not represented by color alone, and existing reduced-motion behavior remains active.

This is not the final Phase 8 accessibility audit. Keyboard, screen-reader and contrast verification across every critical journey remains an explicit exit item.

## Tests

Deterministic unit coverage verifies:

- XP score bounding;
- current streak behavior when the latest rep was yesterday;
- streak reset after a missed day;
- longest-streak retention;
- badge earning/progress without persisted gamification state.

## Remaining Phase 8 work

- offline-safe queued text attempts under poor connectivity;
- end-to-end accessibility audit and fixes across critical journeys;
- performance/bundle review;
- production observability and cost/queue signals;
- final Railway staging smoke test.
