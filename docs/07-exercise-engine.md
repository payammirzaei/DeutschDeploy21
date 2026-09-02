# Exercise engine

**Status:** Accepted baseline

## 1. Objective

The engine turns published content and objectives into interactions without coupling each lesson to bespoke UI code. Adding an item of a supported type requires no deployment. A genuinely new interaction type requires a bounded implementation: contract, materializer, renderer, evaluator, accessibility behavior, analytics, and tests.

## 2. Concepts

- **Exercise type:** registered capability such as multiple choice.
- **Activity blueprint:** editorial configuration of objective, content, constraints, hints, evaluator, and difficulty.
- **Activity instance:** immutable learner-facing prompt with exact choices, accepted answers or rubric, randomization seed, versions, and personalization inputs.
- **Attempt:** one submitted response.
- **Evaluation:** versioned judgment of one attempt.

This separation makes results reproducible and permits later re-evaluation.

## 3. Contract

```ts
interface ExerciseType<B, I, A> {
  type: string;
  contractVersion: number;
  validateBlueprint(input: B, context: ValidationContext): ValidationResult;
  materialize(input: MaterializationInput<B>): I;
  normalizeAnswer(answer: A, instance: I): NormalizedAnswer;
  evaluateDeterministically?(
    answer: NormalizedAnswer,
    instance: I,
    policy: EvaluationPolicy
  ): EvaluationResult;
  getLearningEvidence(instance: I, result: EvaluationResult): LearningEvidence[];
}
```

The frontend renderer registry consumes the same versioned instance contract. Unsupported versions fail clearly.

## 4. Initial types

- Multiple choice
- Matching
- Cloze
- Word ordering with locked chunks
- Conjugation
- Controlled/open translation
- Error correction
- Short answer
- Guided speaking
- Free speaking
- Stateful interview response

## 5. Materialization

Materialization is deterministic given blueprint version, learner context snapshot, content versions, seed, and generator version. The instance stores enough data to render after source content is superseded.

It filters incompatible/archived content, recently overused distractors, ambiguous choices, unverified personalized claims, and inappropriate difficulty.

## 6. Distractors

Preferred order: editor-approved, rule-generated from compatible content, validated AI-proposed, or no exercise if ambiguity remains. Distractors must be plausible, valid, distinct, and not accidentally correct.

## 7. Normalization

May normalize Unicode, whitespace, configured punctuation, accepted spelling, token chunks, and locale formats. It must not remove information that is itself the target, such as noun capitalization.

## 8. Evaluation

- **Deterministic:** exact variants, sets, sequences, structural checks.
- **Rule-assisted:** morphology, required keywords/connectors, duration.
- **AI-assisted:** semantic equivalence and open response quality.
- **Human/editor:** override and benchmark labeling.

Every result declares evaluator type/version, confidence, and evidence.

## 9. Partial credit and evidence

One activity can provide separate evidence for Perfekt, vocabulary, structure, relevance, and comprehensibility. A total score never erases target-specific evidence.

## 10. Hints and retries

Hints are typed and ordered: translation, initial letter, word bank, grammar rule, skeleton, and model. Usage reduces evidence strength by policy.

Retries create new attempts. Correctness after full reveal contributes less. Repeated guessing is detectable. Weak targets enter review without forcing the whole lesson to repeat.

## 11. Offline behavior

The PWA may cache safe instances and queue attempts with client-generated idempotency keys. Server ordering remains authoritative. Speech synchronization must be explicit; UI never says saved before durable acknowledgement.

## 12. Accessibility

Every type specifies keyboard operation, semantic labels, focus, error announcement, a non-drag alternative, transcript behavior, reduced motion, and color-independent feedback.

## 13. Events

Standard events include `activity_presented`, `hint_requested`, `attempt_submitted`, `evaluation_completed`, `feedback_opened`, `retry_started`, `activity_skipped`, and `activity_abandoned`.

## 14. Adding a type

Define purpose; version schemas; implement validation/materialization; implement evaluator; map evidence; build responsive accessible renderer; define offline behavior/events; add editor preview; add unit, property, contract, accessibility, and end-to-end tests; document limits; release safely.

The core content, lesson, enrollment, and progress models must not change merely to recognize the new type.
