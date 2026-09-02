# Product requirements

**Status:** Accepted baseline  
**Scope:** Full target vision with phased delivery

## 1. Personas

### Learner
Consumes lessons, completes exercises, records answers, receives feedback, reviews weak material, and monitors readiness.

### Content editor
Creates and relates verbs, phrases, grammar patterns, questions, examples, rubrics, lessons, and course releases. In the first release, learner and editor are the same person.

### Administrator
Manages access, configuration, provider status, imports, backups, and publishing permissions.

The initial private release may expose a simplified interface, but authorization concepts remain explicit.

## 2. Core user journeys

### First-run setup
1. User enters the private application.
2. User reviews the course goal and commits to a daily duration.
3. User completes a lightweight baseline assessment.
4. System creates an enrollment and initial review state.
5. User receives Day 1 with a clear estimated duration.

### Daily learning
1. Dashboard shows today’s new work, due reviews, streak, and readiness.
2. Learner completes a warm-up review.
3. Learner studies new concepts.
4. Learner completes controlled exercises.
5. Learner produces written and spoken answers.
6. System records attempts and updates mastery.
7. Day summary identifies wins, weak concepts, and next review.

### Content authoring
1. Editor creates or imports a content item.
2. Validation checks required language and linguistic fields.
3. Editor adds examples and relationships.
4. Exercise previews are generated.
5. Editor assigns content to reusable learning objectives.
6. Draft curriculum release is previewed.
7. Publish creates immutable versions and an auditable release.

### Mock interview
1. Learner selects guided, practice, or realistic mode.
2. Interview session receives a blueprint.
3. Questions are selected by domain, difficulty, and weak areas.
4. Follow-ups are selected from deterministic rules or AI suggestions.
5. Speech is transcribed asynchronously.
6. Answer receives language and interview feedback.
7. Session report updates readiness evidence.

## 3. Functional requirements

### FR-CONTENT
- Create, update, archive, tag, search, import, export, preview, version, and publish content.
- Support verbs, vocabulary, phrases, grammar patterns, examples, questions, scenarios, concepts, rubrics, and media.
- Relate content many-to-many.
- Store language-specific and locale-specific values separately.
- Validate separable/reflexive/irregular verb behavior.
- Prevent deletion of published content referenced by attempts.
- Support bulk CSV/JSON import with dry-run and error report.
- Keep editorial notes outside learner-visible content.

### FR-CURRICULUM
- Define course, track, module, lesson, objective, activity blueprint, and release.
- Reuse one item in several lessons and tracks.
- Allow prerequisites, optional activities, unlock rules, estimates, and ordering.
- Treat “Day 1” as scheduling metadata, not the identity of a lesson.
- Freeze published course releases for enrolled learners unless migration is explicit.
- Support future adaptive substitutions without rewriting curriculum.

### FR-EXERCISE
- Render and evaluate multiple exercise types from common contracts.
- Support multiple-choice, matching, cloze, word ordering, conjugation, translation, error correction, short answer, guided speaking, free speaking, and interview response.
- Distinguish deterministic and AI-assisted evaluation.
- Store normalized answers and evaluation evidence.
- Permit exercise-type addition with localized module changes.
- Support hints, attempts, partial credit, and explanation.

### FR-PROGRESS
- Record every meaningful attempt append-only.
- Maintain derived mastery snapshots per learner and learning target.
- Schedule reviews using performance, time, hint usage, and response mode.
- Track completion separately from mastery.
- Preserve progress when course ordering changes.
- Rebuild derived state from events when necessary.
- Explain why an item is due.

### FR-SPEECH
- Record audio with consent.
- Upload reliably on unstable mobile connections.
- Process transcription asynchronously.
- Show transcript and allow learner correction.
- Score pronunciation only when supported by the provider and clearly label limitations.
- Store provider metadata, prompt version, model version, latency, and cost.
- Apply configurable retention and deletion.

### FR-INTERVIEW
- Support guided, practice, and realistic modes.
- Use interview blueprints with categories, time limits, and rubric weights.
- Include recovery phrases and learner questions.
- Generate follow-ups grounded in known content and user claims.
- Provide concise immediate feedback plus a detailed session report.
- Compare repeated attempts over time.

### FR-GAMIFICATION
- XP, levels, streaks, badges, goals, and challenges must derive from auditable events.
- Rewards must not alter linguistic correctness.
- Streak repair/freeze must be transparent.
- Practice remains accessible regardless of reward state.

### FR-ADMIN
- Manage content, curriculum releases, imports, provider configuration, and system health.
- Preview learner rendering before publish.
- Show failed background jobs with retry controls.
- Provide backup status and migration version.
- Restrict dangerous actions and require confirmation.

## 4. Non-functional requirements

### Extensibility
- A new content item requires data entry, not deployment.
- A new course composes existing and new content.
- A new exercise type changes only the exercise registry, its contracts, UI renderer, evaluator, and tests.
- A new AI/speech/storage provider implements an existing port.
- A new language uses locale and linguistic extensions, not duplicated product logic.

### Reliability
- No completed attempt is lost due to AI or worker failure.
- AI tasks are idempotent and retryable.
- Database migrations are forward-safe and backed up.
- Core text learning remains available during provider outages.

### Performance targets
- Cached dashboard API p95 under 500 ms at initial scale.
- Exercise navigation responds locally where possible.
- API write acknowledgement under 800 ms excluding async analysis.
- Audio upload displays progress and safely resumes/retries.
- Initial mobile LCP target under 2.5 seconds on a reasonable 4G connection.

### Accessibility
- WCAG 2.2 AA target.
- Keyboard navigation and visible focus.
- Semantic controls and screen-reader labels.
- Captions/transcripts for audio.
- Do not communicate correctness by color alone.
- Respect reduced-motion preference.

### Internationalization
- UI strings use translation keys from the first implementation.
- Content language, interface language, translation language, and locale are distinct.
- RTL text such as Persian must render correctly beside German.
- Date/time follows user timezone.

### Observability
- Structured logs with correlation IDs.
- Metrics for latency, errors, job depth, provider failure, and cost.
- Traces across API and worker boundaries where practical.
- Learning analytics use an explicit event taxonomy.

### Maintainability
- Typed contracts.
- Automated formatting, linting, unit, integration, contract, and migration tests.
- Dependency direction enforced in CI.
- Architectural changes require ADRs.
- No business logic in HTTP controllers or UI components.

## 5. Initial private release constraints

The first active account is provisioned manually. Public registration, password reset, social login, billing, organizations, and invitations remain disabled. These omissions reduce UI scope but do not justify global singleton rows or hard-coded user IDs.

## 6. Acceptance definition for first usable release

A release is usable when the learner can:

- sign in to the private installation;
- open the correct course enrollment;
- complete text lessons and exercises;
- see persisted progress across devices;
- add a new verb and examples through admin without code changes;
- publish it into a lesson safely;
- receive due reviews;
- record one speaking task;
- complete one mock interview;
- view an explainable readiness report;
- recover safely from worker/provider failure.

## 7. Out-of-scope until explicitly activated

- payments;
- public registration;
- teams and organizations;
- instructor marketplace;
- native iOS/Android;
- live calls;
- user-generated public content;
- social leaderboards;
- enterprise SSO;
- custom on-premise deployment.
