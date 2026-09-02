# Phase 5C — Interview drills

**Status:** Implemented and CI verified

## Outcome

Phase 5C moves DeutschDeploy21 from isolated language mechanics into interview-transfer practice.

The learner can now rehearse how an answer is structured without requiring a microphone. This is intentionally different from a full mock interview: the system still provides deterministic, scaffolded interactions, but the learning target is now interview performance rather than only vocabulary or grammar.

The product path becomes:

```text
language recognition
→ active recall
→ sentence construction
→ interview answer structure
→ later: speaking production
→ later: full mock interview
```

## Silent-first product rule

Interview practice must remain useful on a crowded bus, train, office or other environment where speaking is impractical.

Phase 5C therefore uses the same tap, type and ordered-chunk primitives already proven by Silent Mode.

A learner can work on:

- choosing a stronger professional answer;
- organizing an HR response;
- building a STAR story;
- sequencing a technical explanation;
- sequencing an architecture explanation;
- recalling recovery phrases under visible time pressure.

No microphone is required.

## Drill catalog

The first catalog contains 18 curated drills stored in:

```text
content/interview-drills.json
```

There are three drills in each of six families.

### 1. `interview_best_answer`

Purpose: recognize concise, relevant and evidence-oriented interview answers.

Initial themes:

- professional introduction;
- motivation for a role;
- explaining a strength with evidence.

Mastery target:

```text
interview:answer-quality
```

Skill dimension: `answer_quality`.

### 2. `hr_answer_order`

Purpose: construct clear HR answers from ordered semantic chunks.

Initial themes:

- 60-second introduction;
- motivation;
- development / weakness question.

Mastery target:

```text
interview:hr-structure
```

Skill dimension: `hr_structure`.

### 3. `star_builder`

Purpose: make Situation → Task → Action → Result structure automatic.

Initial themes:

- production incident;
- technical disagreement;
- deadline and prioritization.

Mastery target:

```text
interview:star-structure
```

Skill dimension: `star_structure`.

### 4. `technical_explanation_order`

Purpose: explain technical reasoning in a sequence that an interviewer can follow.

Initial themes:

- REST endpoint flow;
- debugging approach;
- slow database query investigation.

Mastery target:

```text
interview:technical-explanation
```

Skill dimension: `technical_explanation`.

### 5. `architecture_sequence`

Purpose: train high-level system explanations before speaking practice begins.

Initial themes:

- web request flow;
- CI/CD pipeline;
- industrial computer-vision pipeline.

Mastery target:

```text
interview:architecture-explanation
```

Skill dimension: `architecture_sequence`.

### 6. `timed_quick_recall`

Purpose: retrieve useful recovery phrases when interview pressure interrupts fluency.

Initial themes:

- asking the interviewer to rephrase;
- asking briefly for thinking time;
- confirming that the question was understood correctly.

Mastery target:

```text
interview:recovery-recall
```

Skill dimension: `recovery_recall`.

The UI exposes a visible countdown. Duration is stored with the attempt as evidence. The first scheduler version does not turn an otherwise correct answer into an incorrect answer merely because the timer reached zero; stricter time-based scoring belongs in the later readiness/mock-interview rubric.

## No invented personal experience

The drill catalog is curated training material, not a claim about the learner's biography.

Phase 5C does not use AI to invent:

- employers;
- projects;
- achievements;
- conflicts;
- production incidents;
- numerical outcomes.

Behavioral and technical templates are generic structures. Personalization to verified learner projects can be introduced later through explicit learner-owned profile data or reviewed content.

## Generalized activity identity

Earlier phases assumed every `activity_instance` originated from a `release_activity` and therefore from a pinned content version.

That assumption is correct for vocabulary/course activities but wrong for a reusable interview skill.

Migration `20260902_0006` introduces source identity:

```text
source_kind
source_key
instance_key
```

The unique runtime identity becomes:

```text
(enrollment_id, source_kind, source_key, instance_key)
```

Existing content activities are backfilled as:

```text
source_kind = release_activity
source_key  = <release_activity UUID>
```

Interview drills use:

```text
source_kind = interview_drill
source_key  = <stable external drill id>
instance_key = interview
```

`release_activity_id` and `content_version_id` are nullable only because non-content sources can now produce immutable activity instances. Existing course activities still require both values in service-level invariants.

## Generalized learning targets

Phase 4 originally identified mastery using:

```text
content_version_id + skill_dimension + production_mode
```

Phase 5C adds a stable `target_key`, `target_kind` and optional `target_label`.

Content targets keep exact immutable content-version identity, for example:

```text
content:<content_version_id>:lexical_recall:production
```

Interview targets use semantic identities such as:

```text
interview:star-structure
```

This avoids fake content rows or fake verbs merely to make interview-skill mastery fit an older schema.

## One attempt pipeline

Phase 5C also closes an evaluator-dispatch gap discovered during self-review of Phase 5B.

All registered exercise families now submit through the same public endpoint:

```text
POST /api/v1/learning/instances/{instance_id}/attempts
```

The attempt service delegates to the exercise registry, which dispatches:

```text
base Silent exercises
advanced Silent exercises
interview drills
```

The route does not contain exercise-specific scoring logic.

This preserves:

- global idempotency;
- append-only attempts;
- deterministic evaluation;
- one transaction boundary;
- mastery event generation;
- review scheduling;
- frozen prompt replay.

## Mastery and review

Interview skills participate in the same event/projection architecture as language targets:

```text
attempt
→ evaluation
→ interview learning target
→ mastery event
→ learner mastery projection
→ review queue
```

Review uses an outer join to content metadata because an interview target may not have a `content_version_id`.

The frozen original activity instance remains the review source. Therefore a STAR ordering miss can later return as a STAR ordering drill rather than degrading into a generic vocabulary card.

## Curriculum isolation

Interview drills are optional transfer practice in Phase 5C.

They do not:

- increment a required course-day submitted count;
- advance `Enrollment.current_day`;
- silently satisfy a required curriculum activity.

The invariant remains:

```text
practice frequency ≠ course completion ≠ correctness ≠ mastery
```

## API surface

Phase 5C adds one read/materialization action:

```text
POST /api/v1/interview-drills/next
```

Submission reuses the existing attempt endpoint.

No family-specific submission endpoints are introduced.

## Web experience

`/drills` is the first Interview Lab workspace.

It provides:

- six visible drill families;
- 18 curated drill rotation;
- session completion counter;
- best-answer choice cards;
- tap-to-order HR, STAR, technical and architecture answers;
- typed recovery recall;
- visible countdown for timed recall;
- immediate deterministic feedback;
- direct continuation to the next interview skill;
- the same shared `ExercisePlayer` used by Practice and Review.

Dashboard promotes Interview Lab as a primary action alongside Silent Practice, Review and the structured course.

## Verification

CI proves:

- migrations `0001` through `0006` apply on PostgreSQL;
- Ruff passes;
- 11/11 backend integration tests pass;
- the existing ten-family Silent Mode integration test passes through the real registry dispatcher;
- 18 interview drills rotate through all six families;
- all 18 submit through the existing attempt endpoint;
- six distinct `interview_skill` mastery dimensions are projected;
- interview drills do not alter `current_day`;
- interview drills do not alter required day submitted counts;
- review replay is exercise-generic rather than MCQ-specific;
- OpenAPI exports the generalized contracts;
- generated TypeScript succeeds;
- `/drills`, `/practice` and `/review` pass ESLint, strict typecheck and Next.js production build.

## Deliberately deferred

Phase 5C is not yet a full mock interview.

Deferred work includes:

- free-form long text answer evaluation;
- speech capture and transcription;
- pronunciation and fluency feedback;
- dynamic interviewer follow-up questions;
- project-specific answer personalization;
- role-specific interview sessions;
- strict response-time scoring;
- readiness score and before/after comparison;
- AI-assisted evaluation with stored evidence and rubric versions.

Those features should reuse the interview-skill target identities introduced here rather than create a parallel progress system.
