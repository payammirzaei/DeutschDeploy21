# Phase 5D — Full 21-day curriculum

**Status:** Implementation / CI verification

## Outcome

Phase 5D turns the existing learning engine into the complete deterministic 21-day Software Developer interview path.

The important change is not merely that more days exist. The release is now a version-controlled, validated curriculum manifest that combines:

- the 100-verb foundation;
- all ten deterministic silent exercise families;
- structured interview-transfer drills;
- immutable release pinning;
- explicit release migration;
- exact historical carry-over rules;
- the existing attempt, mastery and spaced-review architecture.

The path becomes:

```text
Days 1–3   professional foundation
Days 4–6   contribution and delivery
Days 7–10  architecture and reasoning
Days 11–14 problems, collaboration and behavior
Days 15–17 role depth and interview transfer
Days 18–20 mixed interview performance
Day 21     deterministic final validation
```

Speech and open-ended mock interviews remain later phases.

## Curriculum as version-controlled data

The canonical v2 manifest lives at:

```text
content/curriculum/software-interview-21d.v2.json
```

Runtime code does not contain the 21-day schedule.

The checked-in compact manifest is expanded into normalized release activities before publication. Each normalized activity declares a source kind and stable external source key.

Content activity:

```text
source_kind = content
source_key  = verb.external_id
exercise_type = registered deterministic exercise
```

Interview activity:

```text
source_kind = interview_drill
source_key  = interview drill external_id
exercise_type = drill family
```

## Release v2 invariants

The compiler rejects v2 unless all of these remain true:

- exactly 21 ordered days exist;
- Days 1–14 introduce exactly seven content items each;
- Day 15 introduces exactly two final content items;
- Days 1–15 introduce exactly 100 unique starter verbs;
- the 100 introduced IDs equal the complete starter catalog;
- every content exercise type is registered;
- every referenced interview drill exists;
- all 18 curated interview drills receive curriculum coverage;
- the final release contains exactly 133 required activities.

The day-load shape is:

```text
Days 1–14: 7 activities/day
Days 15–21: 5 activities/day
```

Total:

```text
14 × 7 + 7 × 5 = 133
```

## Coverage

### Days 1–3 — Professional foundation

The original 21 MCQ activities are retained semantically and continue to pin the same content versions when v1 and v2 are created from the same published catalog.

This deliberate compatibility boundary permits exact historical carry-over for existing learners.

### Days 4–14 — Controlled production

The remaining starter verbs rotate across all ten proven deterministic families:

- meaning multiple choice;
- reverse typing;
- Partizip II choice;
- auxiliary choice;
- sentence order;
- meaning matching;
- example cloze;
- usage error spotting;
- full Perfekt typing;
- phrase building.

The structured course therefore no longer means “MCQ only”.

### Day 15 — Final vocabulary and transfer

The final two starter verbs are introduced, bringing the unique introduction count to 100.

Structured interview activities begin inside the required course.

### Days 16–20 — Role depth and mixed performance

The course mixes review-strength language activities with curated HR, behavioral, backend/database, DevOps, architecture, computer-vision and recovery drills.

### Day 21 — Deterministic validation

The final deterministic day revisits introduction, STAR structure and architecture explanation before the product moves into speech and later full mock-interview evidence.

This is not presented as a final spoken-interview score because speech evidence does not exist yet.

## Migration 0007

Migration:

```text
20260902_0007_full_curriculum_release.py
```

adds:

```text
course_releases.manifest_checksum
release_activities.source_kind
release_activities.source_key
```

and makes `release_activities.content_version_id` nullable only for non-content release sources.

Existing release activities are backfilled as content sources.

The downgrade deliberately refuses to proceed while non-content release activities exist. It does not delete learner curriculum data merely to satisfy a schema rollback.

## Immutable release publication

CourseRelease v2 stores the SHA-256 checksum of the normalized canonical manifest.

If v2 is already published and checked-in data later produces a different checksum, runtime refuses to mutate the published release:

```text
v2 checksum mismatch
→ fail publication/ensure path
→ author v3 instead
```

Published curriculum therefore follows the same immutable-history rule as published content.

## Existing v1 learners

The original CourseRelease v1 remains:

```text
3 days
21 required activities
```

Phase 5D does not silently repin an existing active v1 enrollment.

The learning home exposes:

```text
release_version
latest_release_version
upgrade_available
```

Upgrade is explicit:

```text
POST /api/v1/learning/upgrade
```

After a successful upgrade:

- the v1 enrollment becomes `superseded`;
- a v2 enrollment becomes active;
- v1 attempts remain attached to v1;
- no attempt or evaluation is copied;
- no mastery event is fabricated;
- current v2 position is recomputed from compatible historical course work.

## Carry-over rule

A v2 content activity is considered historically submitted only when an earlier course release contains an actual submitted course attempt with:

```text
same user
same course
lower release version
instance_key = course
same pinned content_version_id
same exercise_type
```

This means:

```text
same verb but different published version → no carry-over
same content version but different exercise family → no carry-over
optional Silent Practice attempt → no carry-over
optional Interview Lab attempt → no carry-over
```

Only exact compatible required course work can satisfy a newer release activity.

The old attempt remains the evidence source.

## Generalized release activities

`ReleaseActivity` now describes either content or an interview drill.

Content source:

```text
ReleaseActivity
→ exact ContentVersion
→ registered exercise materializer
→ immutable ActivityInstance
```

Interview source:

```text
ReleaseActivity
→ stable interview drill external ID
→ version-controlled drill blueprint
→ immutable course ActivityInstance
```

Course interview instances have:

```text
source_kind = interview_drill
instance_key = course
release_activity_id = required release activity
content_version_id = null
```

Optional Interview Lab instances keep:

```text
instance_key = interview
```

This isolation prevents optional drill frequency from satisfying curriculum completion or altering optional drill rotation.

## One submission path

Phase 5D removes the old course/advanced submission split.

Every deterministic activity now submits through:

```text
POST /api/v1/learning/instances/{instance_id}/attempts
```

The learning service delegates scoring to the exercise registry, which already dispatches:

- base content exercises;
- advanced content exercises;
- interview drills.

The same transaction then persists:

```text
Attempt
→ Evaluation
→ mastery evidence
→ review scheduling
→ curriculum completion update when instance_key = course
```

There is no exercise-specific public submission API.

## Silent Practice isolation

The v2 release contains non-content interview activities, so Silent Practice now explicitly selects only:

```text
ReleaseActivity.source_kind = content
content_version_id IS NOT NULL
```

Course breadth therefore cannot leak unsupported non-content activities into the optional vocabulary practice selector.

## Learning UI

`/learn` now renders the complete 21-day release.

The page provides:

- 21-day progress;
- 133 required-activity denominator;
- full day rail;
- release version;
- explicit v1→v2 upgrade card;
- course-complete state;
- shared `ExercisePlayer` for all supported deterministic content and interview interactions;
- immediate deterministic feedback;
- durable resume state.

The UI no longer owns MCQ rendering logic.

`ExercisePlayer` remains the shared renderer used by Learning, Silent Practice, Review and Interview Lab.

## Completion versus mastery

The existing product invariant remains unchanged:

```text
submission completion ≠ correctness ≠ mastery
```

A wrong required answer may complete its curriculum slot and advance the day while producing weak mastery evidence and an earlier review schedule.

This avoids retry-until-correct progress inflation.

## Validation and tests

Critical Phase 5D tests cover:

- manifest shape and exact counts;
- 100 unique starter verbs;
- all ten deterministic content exercise families;
- all 18 interview drills;
- immutable v1 preservation;
- explicit v1→v2 migration;
- exact course-work carry-over;
- 21-day v2 shape and 133 activity total;
- course-level interview drill materialization and submission;
- day progression after submissions;
- idempotent attempts;
- existing Silent Practice / Interview Lab / Mastery / Review regressions through the full suite.

## Deferred

Phase 5D intentionally does not claim completion of later roadmap work:

- guided/open answer text evaluation;
- verified learner-specific story authoring UI;
- audio capture;
- transcription;
- pronunciation/fluency evidence;
- stateful mock interviewer;
- adaptive follow-ups;
- baseline/final spoken comparison;
- readiness score;
- missed-day workload replanning polish.

These capabilities should consume the 21-day release and existing target/evidence model rather than fork a parallel curriculum system.
