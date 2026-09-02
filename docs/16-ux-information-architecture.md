# UX, information architecture, and design system

**Status:** Proposed baseline

## 1. Experience goal

DeutschDeploy21 should feel focused, encouraging, and fast, but not childish. The learner is a professional under interview pressure. The UI reduces planning effort, makes progress understandable, and moves from supported learning to independent speaking.

## 2. Primary navigation

Mobile bottom navigation:

- **Today:** daily plan, resume, due reviews.
- **Path:** 21-day course map and modules.
- **Practice:** review, verbs, questions, speaking, weak areas.
- **Interview:** guided/practice/realistic sessions and reports.
- **Progress:** readiness, mastery, streak, history.

Profile/settings and admin are secondary. Admin must not clutter the learner experience.

Desktop may use a side rail while retaining identical information architecture.

## 3. Core screens

### Today
Greeting, day objective, estimated time, resume button, due-review count, required activities, deferred speaking, and a concise previous-session insight.

### Learning path
Vertical module path, day states, prerequisites, output for each day, and clear distinction between completed and mastered.

### Lesson
Persistent progress, one focused activity at a time, explanation on demand, autosaved checkpoint, exit option, and accessible feedback.

### Practice hub
Due review first, then quick practice by capability, verb catalog, question bank, mistakes, saved answers, and speaking.

### Interview
Mode selector, duration/category configuration, equipment check, consent, active turn, preparation timer, recording, processing state, report, and comparison.

### Progress
Readiness dimensions with evidence/confidence, mastery distribution, weak targets, speaking time, baseline comparison, and recommended next action.

### Admin
Catalog, editor, imports, validation, previews, curriculum builder, releases, jobs/providers, and system health.

## 4. State language

Every resource uses explicit states. Avoid vague spinners.

Examples:

- Draft / Ready / Published / Superseded
- Not started / In progress / Completed
- New / Learning / Due / Stable / Mastered / Lapsed
- Uploading / Uploaded / Processing / Feedback ready / Failed with retry

The UI explains what the state means and whether user action is required.

## 5. Learning interaction principles

- One main decision per screen.
- Feedback appears near the answer and identifies the next correction.
- German is primary during production; Persian explanation is available without navigation loss.
- Model answers are hidden until useful effort occurs.
- Speaking preparation and response time are visible but not anxiety-inducing.
- The learner can replay their recording, inspect transcript, correct transcript, and retry.
- Progress survives refresh and device changes.
- Provider delay never traps navigation.

## 6. Visual direction

Professional, energetic, and technically modern. Use restrained color, strong typography, generous touch targets, and subtle depth. Avoid copying Duolingo assets, characters, trade dress, or exact interaction design.

Suggested semantic tokens:

- background/surface/elevated;
- text primary/secondary/muted/inverse;
- brand;
- success/warning/error/info;
- mastery new/learning/due/stable/mastered;
- focus;
- border/divider.

Theme values are tokens, never scattered literal colors.

## 7. Typography and multilingual layout

Select typefaces supporting German and Persian clearly. Components must handle LTR and RTL fragments within one screen. Language direction belongs to the text container, not the whole application by assumption.

Use logical CSS properties. Test long German compound words, Persian translations, mixed technical terms, and dynamic font scaling.

## 8. Responsive behavior

Design first for 360–430 px widths. Primary controls meet touch-size requirements. Desktop improves density but does not introduce required hover interactions.

Tables in admin use responsive alternatives or controlled horizontal scroll. Exercise interactions never require precision dragging.

## 9. Accessibility

Target WCAG 2.2 AA. Provide semantic headings, landmarks, labels, focus management, keyboard shortcuts only as enhancement, screen-reader announcements, contrast, non-color feedback, captions/transcripts, reduced motion, and zoom support.

Recording UI exposes its state textually. Timers allow accommodation in non-realistic modes.

## 10. Empty, error, and offline states

Every major screen defines loading, empty, partial, failure, permission, offline, and retry states.

Examples:

- no due reviews: offer targeted practice;
- worker delayed: show saved attempt and permit continuation;
- microphone denied: explain browser steps and allow text fallback;
- offline: show cached availability and synchronization queue;
- content release missing: fail safely with support code.

## 11. PWA

The PWA provides installability, app shell caching, safe text-session resilience, update notification, and mobile icons. It does not claim full offline speech processing.

An update must not discard an active answer. New service workers activate through a controlled user-safe flow.

## 12. Design-system structure

- tokens;
- primitives;
- accessible UI components;
- learning components;
- exercise renderers;
- charts/report components;
- admin components;
- patterns and page templates.

Components use variants and semantic props. Domain rules stay outside visual components.

## 13. UX telemetry

Measure time to first activity, resume success, abandonment, hint timing, feedback expansion, recording failures, processing wait, retry, and navigation confusion. Do not use manipulative engagement metrics.

## 14. Usability acceptance

Before a major release, test on an Android mobile viewport, desktop keyboard, mixed Persian/German content, slow connection, microphone denial, provider delay, and long content. A learner must complete a day and find due review without instruction.
