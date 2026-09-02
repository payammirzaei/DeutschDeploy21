# Phase 7 — Mock interview and readiness

**Status:** Implemented and CI verified on PR #10; merge pending.

## 1. User outcome

Phase 7 converts isolated drills and speaking repetitions into a durable interview performance loop:

```text
Choose mode → materialize frozen session → answer turn
→ deterministic evaluation → contextual follow-up when needed
→ continue/resume → readiness report → baseline/final comparison
```

The learner can answer by text or voice. Voice turns reuse the Phase 6 speech attempt, media, transcription and feedback pipeline rather than creating a parallel recording system.

## 2. Interview modes

### Guided

- intent is visible;
- hints are available immediately;
- optimized for learning answer structure;
- readiness confidence is intentionally lower than realistic mode.

### Practice

- question is primary;
- hints are available only on request;
- stronger independence signal than Guided;
- designed as the bridge between drills and a realistic interview.

### Realistic

- no hints;
- preparation time is defined by the frozen blueprint;
- contextual follow-ups remain possible;
- strongest readiness-confidence multiplier.

A session also has a purpose: `practice`, `baseline`, or `final`.

## 3. Version-controlled blueprint

`content/mock-interview-blueprint.v1.json` is canonical source data for the first Software Developer A2–B1 mock interview.

It defines:

- blueprint key/version;
- language and target CEFR;
- rubric version;
- mode configuration;
- ordered core question pools;
- category;
- learner-visible question;
- intent;
- hints;
- target duration;
- deterministic required-signal groups;
- curated contextual follow-up;
- optional technical-term vocabulary.

A new session stores both the blueprint identity/checksum and a frozen plan. Editing a future blueprint version must not rewrite an existing interview.

## 4. Durable data model

Migration `20260902_0009` adds four tables.

### `mock_interview_sessions`

Stores owner, pinned blueprint identity/checksum, mode, purpose, deterministic seed, frozen plan, status, current turn and timestamps.

### `mock_interview_turns`

Stores one durable learner-facing question snapshot per turn. A turn records:

- stable position key;
- question/category/source identity;
- frozen question payload;
- active/pending/answered state;
- follow-up parent/reason;
- hint usage;
- optional linked `SpeechAttempt`;
- answer text/source;
- answer idempotency key;
- answer timestamp.

The unique session/position constraint prevents duplicate contextual turns. Text answer idempotency prevents double submission.

### `mock_interview_turn_evaluations`

Stores the exact rubric version, overall score, interpretable dimensions, evidence, summary and next action for one answered turn.

### `mock_readiness_reports`

Stores the completed-session readiness result, confidence, dimensions, strengths, priorities and optional baseline comparison.

Readiness is intentionally separate from learner mastery. Knowing vocabulary reliably does not prove the learner can perform under interview conditions.

## 5. Turn state machine

```text
pending → active → answered
             ↓
       optional follow-up inserted
             ↓
      next pending turn active
             ↓
       no pending turns remain
             ↓
          completed
```

Only one turn is intended to be active at a time. A completed session is immutable as interview evidence.

## 6. Contextual follow-ups

Phase 7 v1 does not require an AI provider.

Each core blueprint question may include one curated follow-up. A weak answer below the mode-specific threshold can materialize that exact frozen follow-up:

- Guided: below 60;
- Practice: below 72;
- Realistic: below 80.

The follow-up references its parent turn and records `clarify_weak_answer` as the reason. Duplicate answer submission cannot create duplicate follow-ups.

This deterministic fallback is the product baseline even after model-generated follow-ups are introduced later.

## 7. Deterministic rubric v1

The first turn evaluator is intentionally transparent. It derives evidence from the confirmed answer text and scores:

- relevance to required answer signals;
- visible answer structure;
- concision against target duration/word volume;
- technical or concrete specificity;
- communication proxy;
- independence from hints;
- optional Phase 6 speech-text delivery score when a spoken answer is used.

The evaluator does **not** claim pronunciation, accent, CEFR speaking level or truthfulness about facts it cannot verify.

Every turn returns one concrete next action. Evidence fields include word count, target word count, matched signal groups, structure markers, matched technical terms, filler count and hint usage.

## 8. Readiness report

At completion, the session produces a report across interview categories plus communication and independence.

Overall readiness is based on the core interview turns. Follow-ups are additional evidence but do not silently increase the denominator of the planned interview.

Confidence is not the same as score. It is derived from:

- core-question coverage;
- mode realism;
- amount of speech evidence;
- independence from hints.

A strong Guided session can therefore have a high score but lower readiness confidence than the same performance in Realistic mode.

## 9. Baseline and final comparison

A `final` session searches only for a compatible earlier completed baseline with:

- same user;
- same blueprint key;
- same interview mode;
- compatible rubric version boundary.

The final report stores baseline report identity, baseline score, overall delta and per-dimension deltas. Historical baseline evidence is never rewritten.

## 10. Phase 6 speech reuse

A mock turn can create a `SpeechAttempt` with:

```text
source_kind = mock_interview_turn
source_key = {session_id}:{turn_id}
```

The exact mock question becomes the speech prompt snapshot. Consent remains mandatory.

The existing Phase 6 flow handles:

```text
MediaRecorder → private upload → durable job → worker
→ speech provider → immutable transcript → speech feedback
```

When the transcript is ready, Phase 7 syncs the preferred transcript into the turn evaluation:

1. learner-corrected transcript if present;
2. otherwise raw provider transcript;
3. otherwise manual transcript fallback.

The mock interview never mutates the speech evidence.

## 11. `/mock` UX

The mobile-first page includes:

- Guided / Practice / Realistic selection;
- Practice / Baseline / Final purpose;
- blueprint version and mode metadata;
- recent-session resume;
- session progress;
- one active question at a time;
- contextual follow-up labeling;
- intent only in Guided mode;
- hint request in supported modes;
- text answer path;
- voice consent and direct voice answer path;
- recording timer;
- Phase 6 upload/transcription polling;
- speech-to-turn synchronization;
- previous-turn score and next action;
- final readiness score;
- dimension bars;
- confidence;
- strengths/priorities;
- baseline-to-final delta.

A microphone or provider failure never blocks text interview completion.

## 12. API

Private endpoints under `/api/v1/mock-interviews`:

- `GET /blueprint`
- `POST /sessions`
- `GET /sessions`
- `GET /sessions/{session_id}`
- `POST /sessions/{session_id}/turns/{turn_id}/hint`
- `POST /sessions/{session_id}/turns/{turn_id}/text`
- `POST /sessions/{session_id}/turns/{turn_id}/speech-attempt`
- `POST /sessions/{session_id}/turns/{turn_id}/sync-speech`

Text submission uses `Idempotency-Key`.

## 13. Critical integration coverage

`test_mock_interview.py` verifies:

1. all three modes are exposed;
2. Guided mode exposes intent/hints;
3. a weak answer inserts exactly one contextual follow-up;
4. duplicate answer submission is harmless;
5. Realistic mode rejects hint requests;
6. full realistic baseline session completes and creates a report;
7. full realistic final session compares against the compatible baseline;
8. both reports use rubric v1;
9. mock speech turn creates a real Phase 6 `SpeechAttempt`;
10. Phase 6 manual transcript/feedback can be synced back into the mock turn.

CI run #104 (`33633258951`) verified migrations `0001–0009`, Ruff, all 18 backend tests, OpenAPI export, generated TypeScript, frontend lint/typecheck, and the production Next.js build including `/mock`.

The repository suite also keeps all previous platform, content, curriculum, practice, mastery, review and speech tests green. Speech consent tests were made order-independent after the new mock-speech integration exposed a pre-existing test-isolation assumption.

## 14. AI boundary

Phase 7 deliberately ships without making AI-generated questions, follow-ups or scoring a correctness dependency.

A future `AITextProvider` enhancement may propose a validated contextual follow-up or structured rubric evidence, but:

- the frozen interview session remains canonical;
- learner text is treated as untrusted input;
- personal facts may not be invented;
- malformed model output is rejected;
- deterministic curated follow-up remains available;
- provider outage cannot corrupt or block the session;
- model/rubric changes require explicit versioning.

## 15. Explicit non-goals

Phase 7 does not yet provide:

- full-duplex real-time interviewer voice;
- automatic pronunciation/phoneme scoring;
- model-generated truthfulness claims;
- public multi-user interview sharing;
- employer-specific question generation from scraped data;
- an opaque single-number hiring prediction.

The result is a private, durable, versioned interview simulator with interpretable evidence and a clean path to future AI augmentation.
