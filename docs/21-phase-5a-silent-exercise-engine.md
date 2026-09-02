# Phase 5A — Silent multi-exercise engine

**Status:** Implemented / CI verified

## Outcome

Phase 5A makes DeutschDeploy21 useful when speaking is socially or physically impractical: a crowded bus, train, office, waiting room, queue, or late-night shared space.

Silent practice is a first-class learning mode, not a fallback version of speaking practice. It uses the same immutable content versions, durable attempts, deterministic evaluations, mastery projection and spaced-review scheduler as the structured course.

## Product rule

A learner must be able to make meaningful interview-German progress without using a microphone.

Silent practice therefore prioritizes:

- one-handed tap interactions;
- keyboard-friendly recall;
- short 30–90 second drills;
- no drag-only requirement;
- immediate deterministic feedback;
- unlimited optional repetition without falsifying curriculum completion.

## Initial exercise registry

The first registry version supports five deterministic types:

1. `meaning_multiple_choice`
   - German verb → Persian meaning;
   - skill dimension: `meaning_recognition`;
   - production mode: `recognition`.

2. `reverse_typing`
   - Persian meaning → typed German verb;
   - skill dimension: `lexical_recall`;
   - production mode: `production`.

3. `perfect_participle_choice`
   - infinitive → correct Partizip II;
   - skill dimension: `perfect_participle`;
   - production mode: `recognition`.

4. `auxiliary_choice`
   - infinitive → `haben` or `sein`;
   - skill dimension: `perfect_auxiliary`;
   - production mode: `recognition`.

5. `sentence_order`
   - shuffled tokens from the exact published German example → correct sentence order;
   - skill dimension: `sentence_structure`;
   - production mode: `construction`;
   - tap-to-build is the canonical mobile interaction; drag is not required.

## Instance model

Course activities and optional practice share the existing `activity_instances` table, but Phase 5A adds `instance_key`.

The identity becomes:

```text
(enrollment_id, release_activity_id, instance_key)
```

Examples:

```text
course
silent:meaning_multiple_choice
silent:reverse_typing
silent:perfect_participle_choice
silent:auxiliary_choice
silent:sentence_order
```

This preserves the exact pinned `content_version_id` while allowing multiple immutable interaction variants over one curriculum target.

A silent instance never replaces or mutates the required `course` instance.

## Progress isolation

Optional practice must not complete curriculum work implicitly.

Day progress and day completion therefore count only attempts belonging to:

```text
ActivityInstance.instance_key == "course"
```

A learner may practice a Day 1 verb twenty times in Silent Mode and still have the Day 1 required course activity untouched.

This keeps these concepts separate:

```text
practice frequency != curriculum completion != correctness != mastery
```

## Generic attempt contract

The attempt API now accepts multiple deterministic answer shapes:

```json
{ "choice_id": "..." }
```

```json
{ "text": "entwickeln" }
```

```json
{ "token_ids": ["...", "...", "..."] }
```

The exercise registry owns normalization and evaluation. Routes do not contain exercise-specific scoring logic.

## Deterministic materialization

Each materializer receives an exact content version and release context.

It stores the full immutable prompt and answer key in `activity_instances` and computes the existing prompt checksum.

Examples:

- meaning distractors come from other pinned Persian translations in the same release;
- Partizip II distractors come from other pinned verb versions in the same release;
- auxiliary choice uses the published `perfect_auxiliary` field;
- sentence ordering uses the exact published `VersionExample.text_de` and stable token IDs;
- token shuffle and choice ordering are hash-stable rather than random-at-render-time.

Historical attempts therefore remain reproducible after content is edited and republished.

## Silent scheduler

`POST /api/v1/practice/silent/next` selects the next optional practice activity.

The scheduler:

1. ensures the starter learning release exists;
2. reads the learner's pinned release activities;
3. rotates across the five registered silent exercise types;
4. within a type, prefers targets with fewer silent attempts;
5. deterministically breaks ties;
6. skips content that cannot safely materialize a requested exercise type.

The first five successful silent requests are therefore designed to expose interaction variety instead of five consecutive multiple-choice cards.

## Mastery integration

Phase 4 originally projected every attempt onto `meaning_recognition`.

Phase 5A maps evidence by exercise type. The same verb can now have independent mastery projections such as:

```text
entwickeln / meaning_recognition
entwickeln / lexical_recall
entwickeln / perfect_participle
entwickeln / perfect_auxiliary
entwickeln / sentence_structure
```

This is intentional. Recognizing a translation does not prove that a learner can actively recall the German word or reconstruct a sentence containing it.

Each dimension still uses the Phase 4 append-only event → rebuildable projection → review queue flow.

## Review integration

Review payloads are now exercise-generic. They carry:

- `exercise_type`;
- `contract_version`;
- `prompt_checksum`;
- the exact frozen `prompt`;
- target/review metadata.

The web app uses one shared exercise player for Silent Practice and Review. A typing or sentence-order miss can therefore return later in its original interaction form instead of degrading into a generic MCQ.

## Web experience

`/practice` is the first dedicated Silent Mode workspace.

It provides:

- a visible five-type exercise mix;
- a session exercise counter;
- large mobile tap targets;
- typed recall without autocorrect/spellcheck interference;
- tap-to-build sentence ordering;
- remove/reset controls as a non-drag accessibility path;
- immediate correct/review feedback;
- one-tap continuation to the next drill;
- links to structured learning and due review.

Dashboard makes Silent Mode a primary product action rather than hiding it inside the course.

## Migration 0005

`20260902_0005_silent_exercise_engine.py`:

- adds non-null `activity_instances.instance_key` with a migration-time `course` default;
- replaces the old two-column activity-instance uniqueness constraint with the new keyed identity;
- removes the server default after backfill;
- downgrade removes non-course practice variants before restoring the Phase 3 uniqueness constraint.

## Verification

CI verifies:

- PostgreSQL migrations 0001–0005;
- Ruff;
- 10/10 backend tests;
- all five initial silent exercise types materialize and submit through one attempt endpoint;
- Silent Mode leaves course submitted counts and `current_day` unchanged;
- silent attempts create five distinct mastery dimensions;
- OpenAPI export and generated TypeScript contracts;
- frontend ESLint and strict TypeScript;
- Next.js production build for `/practice`, `/review` and the shared exercise player.

## Deliberately deferred

The registry is intentionally extensible. The next exercise additions should include:

- multi-pair matching;
- cloze / fill-the-gap;
- error spotting and correction;
- conjugation production;
- phrase-builder and interview-answer ordering;
- scenario choice / better-answer comparison;
- quick recall with controlled self-assessment;
- listening puzzles in the speech phase;
- speaking exercises using the same evidence boundary.

Those additions should not require another redesign of attempts, activity instances, mastery targets or review rendering.
