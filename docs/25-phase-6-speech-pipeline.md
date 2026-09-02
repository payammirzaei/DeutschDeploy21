# Phase 6 — Durable speech pipeline

**Status:** Implemented and CI verified; dedicated Railway deployment verification pending.

## 1. User outcome

Phase 6 adds a real Speak Mode without turning voice into a prerequisite for learning. A learner can still complete the full product silently on a bus, train or in an office. When speaking is practical, `/speak` adds a durable repetition loop:

```text
Prompt → consent → record → preview → upload → durable job
→ transcription → raw transcript → learner correction → feedback → repeat
```

The central invariant is that a provider or network failure must not erase the learner's attempt.

## 2. Scope

The first speech release includes:

- eight curated German software-interview speaking prompts;
- explicit voice-processing consent;
- browser `MediaRecorder` capture and local preview;
- text fallback when microphone access is unavailable or speaking is impractical;
- private audio storage behind a storage port;
- durable asynchronous transcription jobs;
- a provider-neutral speech-to-text port;
- an OpenAI transcription adapter configured by environment;
- immutable raw provider transcripts;
- append-only learner transcript corrections;
- transparent text-level feedback;
- transcription retry after provider failure;
- raw-audio deletion without deleting derived transcript/feedback;
- recent speaking-repetition history.

Real-time conversational voice, pronunciation scoring, accent scoring, phoneme alignment and AI-generated open-ended interview grading are intentionally outside this phase.

## 3. Data model

Migration `20260902_0008` introduces six durable tables.

### `speech_consents`

Records user consent against a versioned policy. Consent can be revoked without rewriting historical attempts.

### `media_objects`

Stores private media metadata only:

- owner;
- storage backend and opaque key;
- MIME type;
- byte size;
- SHA-256 checksum;
- client-measured duration;
- lifecycle state and deletion timestamp.

The database never stores public audio URLs.

### `speech_attempts`

One immutable prompt snapshot per speaking repetition. The row stores source identity, prompt checksum, target language/duration, media reference, transcription job reference, retry count and explicit processing state.

### `speech_transcripts`

Append-only transcript revisions. `provider_raw` is preserved as provider evidence. `learner_corrected` and `manual` are separate revisions; correction never overwrites the raw provider output.

### `provider_invocations`

Auditable provider-call metadata:

- purpose;
- provider/model;
- template version;
- request checksum;
- correlation ID;
- status and latency;
- optional usage/cost fields;
- retained output reference;
- bounded error code.

Secrets and raw media are never logged into this table.

### `speech_feedback`

Feedback is versioned against an exact transcript revision. Re-scoring a corrected transcript produces new feedback without invalidating previous evidence.

## 4. State model

Speech attempts use explicit learner-visible states:

```text
created
  → queued
  → transcribing
  → feedback_ready

queued/transcribing → failed → queued (explicit retry)
```

`failed` means transcription failed, not that the learner's attempt disappeared.

Media has its own lifecycle (`verified`, `deleted`) so raw-audio retention is independent from transcript and feedback retention.

## 5. API

Private endpoints under `/api/v1/speech`:

- `GET /prompts`
- `GET /consent`
- `POST /consent`
- `POST /attempts`
- `GET /attempts`
- `GET /attempts/{attempt_id}`
- `PUT /attempts/{attempt_id}/audio`
- `POST /attempts/{attempt_id}/retry-transcription`
- `POST /attempts/{attempt_id}/manual-transcript`
- `POST /attempts/{attempt_id}/correct-transcript`
- `DELETE /attempts/{attempt_id}/audio`

Audio upload is a bounded raw request body. The API validates ownership, consent, MIME type, size and optional duration before durable processing begins.

## 6. Durable async boundary

Speech transcription reuses the Phase 1 job architecture.

```text
API
  → save media
  → create PostgreSQL PlatformJob(speech.transcribe)
  → commit attempt/media/job
  → signal Redis

Worker
  → claim PostgreSQL job
  → load media through storage adapter
  → invoke speech provider
  → persist provider invocation
  → persist raw transcript
  → persist feedback
  → mark attempt feedback_ready
```

PostgreSQL remains the source of truth. Redis is only a wake-up signal. If Redis is unavailable after the commit, the worker's PostgreSQL fallback can still discover queued work.

## 7. Media storage

### Development and CI

`FilesystemMediaStorage` is used with a local shared directory. Docker Compose mounts the same `speech_media` volume into the API and worker containers.

### Railway staging/production

Production uses `RailwayS3MediaStorage` against a Railway Storage Bucket. Railway Buckets expose an S3-compatible API and provide the variables used by the adapter:

- `BUCKET`
- `ACCESS_KEY_ID`
- `SECRET_ACCESS_KEY`
- `REGION`
- `ENDPOINT`

Both API and worker services must receive references to the same private Bucket variables. `MEDIA_STORAGE_BACKEND=railway_s3` is mandatory outside development/test.

This avoids the incorrect assumption that two independent Railway services can safely share local filesystem state.

The first implementation proxies upload through FastAPI so consent, bounds, checksum and durable metadata are enforced in one place. Direct browser-to-Bucket presigned multipart upload is a later optimization if media size or API bandwidth becomes material.

## 8. Speech provider port

`SpeechToTextProvider` separates the learning domain from vendor APIs.

Current adapters:

- `MockSpeechToTextProvider` — deterministic development/CI only;
- `OpenAISpeechToTextProvider` — production-capable transcription adapter.

Configuration:

```text
SPEECH_TRANSCRIPTION_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_TRANSCRIPTION_MODEL=gpt-4o-transcribe
SPEECH_PROVIDER_TIMEOUT_SECONDS=90
```

The OpenAI model name is configurable so a provider/model migration does not change domain tables or attempt history.

## 9. Transcript integrity

The raw provider transcript is evidence, not an editable text box. The UX shows it separately as immutable.

If transcription is imperfect, the learner edits a separate correction. Feedback then references the corrected transcript. This preserves three distinct facts:

1. what the learner recorded;
2. what the provider heard;
3. what text the learner confirmed was intended.

Manual text fallback follows the same feedback contract but is explicitly marked `manual` and does not pretend pronunciation was assessed.

## 10. Feedback v1

Phase 6 feedback is intentionally deterministic and explainable. It uses saved transcript text plus recorded duration to expose:

- word count;
- lexical variety proxy;
- duration vs target;
- words-per-minute proxy;
- filler-word count;
- structure-marker count;
- concision score;
- structure-signal score;
- fluency proxy;
- output-length score;
- concrete next-repetition action.

`pronunciation_assessed` is always `false` in this version. The product must not claim pronunciation or accent quality from transcript text alone.

This deterministic baseline gives us trustworthy evidence before adding model-based rubrics in the mock-interview phase.

## 11. Privacy and deletion

Voice data is optional and sensitive.

Rules:

- consent is required before attempt creation or transcription;
- Silent Mode and the 21-day course remain usable without consent;
- storage keys are opaque and private;
- no public media URL is persisted;
- provider credentials stay in environment secrets;
- raw audio can be deleted independently;
- deleting raw audio does not silently erase transcript/feedback evidence;
- provider failures expose bounded error codes rather than secrets or raw payloads;
- media ownership is checked on every mutation.

A broader account-level erase/export workflow remains a later privacy feature.

## 12. `/speak` UX

The mobile-first Speak Mode implements:

- consent onboarding;
- prompt rail with category and target duration;
- one-tap recording;
- visible recording timer;
- local audio preview before upload;
- explicit queued/transcribing/failed/feedback-ready states;
- retry after transcription failure;
- immutable raw transcript panel;
- learner correction editor;
- text-only fallback;
- feedback dimensions and next action;
- raw-audio deletion;
- recent speaking repetitions.

Microphone denial never traps the learner. Text fallback remains available on the same screen.

## 13. Tests

Critical integration coverage added in `test_speech_pipeline.py`:

1. consent is required;
2. prompt snapshot/checksum is durable;
3. API uploads audio and commits the job before worker processing;
4. a real worker subprocess consumes the job;
5. deterministic mock provider creates a raw transcript;
6. feedback is attached to that exact transcript;
7. learner correction does not mutate raw provider evidence;
8. feedback moves to the corrected transcript;
9. raw audio can be deleted while derived evidence remains;
10. manual text fallback works without microphone/audio.

The full repository CI still runs previous platform, content, curriculum, Silent Practice, Interview Lab, mastery and review tests.

## 14. Railway deployment checklist

A dedicated DeutschDeploy21 Railway project should contain at least:

- web service;
- API service;
- worker service;
- PostgreSQL;
- Redis;
- one private Storage Bucket.

Before production deployment:

1. connect the repository and `main` branch;
2. attach the Bucket variables to API and worker;
3. set `MEDIA_STORAGE_BACKEND=railway_s3` on API and worker;
4. set the same PostgreSQL and Redis references for API/worker;
5. set `SPEECH_TRANSCRIPTION_PROVIDER=openai`;
6. set `OPENAI_API_KEY` as a Railway secret;
7. run migration `0008` before app traffic;
8. verify `/api/v1/health/ready`;
9. record one short German test answer;
10. confirm API upload → Bucket → worker → provider → transcript → feedback;
11. delete the raw audio and verify the derived transcript remains;
12. inspect logs to ensure no audio bytes, signed URLs or provider secrets are emitted.

At the time this document was written, code support is implemented but a dedicated DeutschDeploy21 Railway project has not yet been provisioned. Existing unrelated Railway projects must not be reused accidentally.

## 15. Explicit non-goals

Phase 6 does not yet provide:

- live streaming transcription;
- full-duplex voice conversation;
- pronunciation/phoneme scoring;
- accent ranking;
- automatic claims about CEFR speaking level;
- AI interviewer orchestration;
- AI-generated final interview readiness score.

Those belong to later phases after this durable recording/transcript foundation is verified.
