# Phase 5B — Exercise explosion

**Status:** Implementation / CI verification

## Outcome

Phase 5B doubles Silent Mode from five deterministic exercise families to ten while preserving the same immutable content, attempt, evaluation, mastery and review architecture introduced in Phases 3–5A.

The learner should now encounter the same interview vocabulary through multiple cognitive operations instead of repeated card shapes:

```text
recognize → recall → match → complete → discriminate → construct → produce
```

No database migration is required for this phase. The Phase 5A keyed `activity_instances` model already supports multiple immutable variants over the same pinned release activity.

## Exercise registry architecture

Phase 5A proved the initial engine. Phase 5B introduces a composition boundary so the base engine does not become one continuously growing conditional file.

```text
Base exercise pack
        +
Advanced exercise pack
        ↓
exercise_registry.py
        ↓
materialize / evaluate / mastery mapping
```

The base pack remains responsible for the original five exercise types. The advanced pack owns the new five families.

The registry exposes the complete Silent Mode set to the scheduler and registers advanced mastery dimensions into the same target mapping used by Phase 4.

## Ten Silent Mode exercise families

### Base pack

1. `meaning_multiple_choice`
   - German verb → Persian meaning
   - skill: `meaning_recognition`

2. `reverse_typing`
   - Persian meaning → typed German infinitive
   - skill: `lexical_recall`

3. `perfect_participle_choice`
   - infinitive → Partizip II
   - skill: `perfect_participle`

4. `auxiliary_choice`
   - infinitive → `haben` / `sein`
   - skill: `perfect_auxiliary`

5. `sentence_order`
   - token-level reconstruction of the exact published interview example
   - skill: `sentence_structure`

### Advanced pack

6. `meaning_matching`
   - three pinned German verbs ↔ three pinned Persian translations
   - tap-first interaction
   - skill: `meaning_association`

7. `example_cloze`
   - exact published interview example with the infinitive removed
   - learner types the missing German verb
   - skill: `contextual_recall`

8. `usage_error_spotting`
   - choose the structurally correct published modal + infinitive sentence
   - deterministic error variants use Partizip II or an invalid `zu + infinitive` after the modal
   - skill: `usage_discrimination`

9. `perfect_form_typing`
   - actively produce `Hilfsverb + Partizip II`
   - answer derives only from published typed verb metadata
   - skill: `perfect_form`

10. `phrase_builder`
    - reorder multi-word chunks from the exact published interview example
    - easier and more fluent than token-level sentence ordering
    - skill: `phrase_fluency`

## No guessed German

Exercise generation must not invent conjugations or grammatical forms that the content model does not explicitly know.

Phase 5B therefore uses only:

- published infinitives;
- published `perfect_auxiliary`;
- published `participle_ii`;
- published Persian translations;
- exact published German examples.

`example_cloze` and `usage_error_spotting` only materialize when the exact infinitive is present in the published example. If a content item does not safely support a family, the scheduler skips that item for that family and tries another pinned release activity.

This is preferred over producing a linguistically plausible but unverified exercise.

## Matching contract

The generic attempt schema gains:

```json
{
  "pair_ids": [
    "left-id:right-id",
    "left-id:right-id",
    "left-id:right-id"
  ]
}
```

The backend validates:

- every source item is answered exactly once;
- every destination item is used exactly once;
- every submitted ID belongs to the frozen prompt;
- the normalized pair set matches the immutable answer key.

The interaction remains one-handed and does not require drag-and-drop.

## Advanced attempt dispatch

The public write surface does not expand.

All ten families still submit through:

```text
POST /api/v1/learning/instances/{instance_id}/attempts
```

The route dispatches advanced optional instances to the advanced deterministic evaluator while preserving:

- global idempotency behavior;
- append-only attempts;
- deterministic evaluations;
- the same mastery projection call;
- the same review scheduler;
- the same transaction boundary.

There is intentionally no `/submit-matching`, `/submit-cloze`, or exercise-specific write API.

## Curriculum isolation

Advanced exercises are optional Silent Mode variants and cannot replace required course activities.

The advanced attempt service rejects an advanced instance if its `instance_key` is `course`.

Therefore:

```text
more practice ≠ fake course completion
```

Ten Silent Mode submissions must leave structured day `submitted_count` and `current_day` unchanged.

## Mastery model

The same verb can now accumulate independent evidence across ten dimensions.

Example:

```text
entwickeln
├── meaning_recognition
├── lexical_recall
├── perfect_participle
├── perfect_auxiliary
├── sentence_structure
├── meaning_association
├── contextual_recall
├── usage_discrimination
├── perfect_form
└── phrase_fluency
```

This prevents an easy recognition success from being treated as proof of active production, contextual recall or phrase fluency.

## Shared web renderer

`ExercisePlayer` now supports four interaction primitives:

```text
choice
text input
ordered chunks
matching pairs
```

Those primitives currently render all ten exercise families in both Practice and Review.

Matching uses two tap columns with clear selected/completed states. Existing sentence and phrase builders use tap/remove/reset rather than drag-only controls.

## Verification target

The Phase 5B integration test must prove:

- the scheduler exposes all ten registered families across a ten-attempt session;
- all ten answers pass through the same public attempt endpoint;
- matching accepts the extended `pair_ids` contract;
- ten distinct mastery dimensions are projected;
- Silent Mode does not change structured course submitted counts;
- Silent Mode does not advance `current_day`;
- OpenAPI exports the new answer contract;
- generated TypeScript accepts matching submissions;
- Practice and Review pass ESLint, strict typecheck and production build.

## Next exercise depth

The next high-value additions should focus less on isolated verb forms and more on interview performance:

- scenario-based best-answer comparison;
- HR answer ordering;
- STAR answer builder;
- architecture explanation sequencing;
- technical vocabulary grouping;
- timed quick recall;
- confidence/self-assessment evidence with safeguards;
- listening discrimination;
- speaking production using the same immutable/evidence boundary.
