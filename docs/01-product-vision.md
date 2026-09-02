# Product vision

**Status:** Accepted baseline  
**Product:** DeutschDeploy21  
**Tagline:** Speak German. Explain Your Work. Get Hired.

## 1. Problem

Software professionals can possess strong technical experience while failing to communicate it in German interviews. General language applications optimize broad vocabulary and everyday scenarios. Conventional interview lists provide passive reading but little retrieval, speaking, personalization, feedback, or retention.

The target learner does not need encyclopedic German first. They need a reliable path from known professional experience to spoken, understandable, job-relevant German.

Core difficulties include:

- converting passive vocabulary into speech under time pressure;
- choosing correct tense and sentence order;
- describing personal contribution rather than only the team’s work;
- explaining architecture without memorizing unnatural paragraphs;
- answering unpredictable follow-up questions;
- recovering from misunderstood questions;
- recognizing repeated weaknesses;
- practicing consistently without manually planning every session.

## 2. Vision

DeutschDeploy21 is a deliberate-practice platform that turns a learner’s real professional history into a structured 21-day German interview program.

It combines:

- curated vocabulary and grammar;
- reusable content relationships;
- adaptive exercises;
- active recall and spaced repetition;
- guided-to-independent speaking;
- HR, behavioral, and technical interview simulations;
- evidence-based readiness reporting.

The application should feel motivating and lightweight like a modern language-learning product, while its learning logic remains specific to professional interviews.

## 3. Initial learner

The first learner is a software engineer preparing for German interviews, with experience spanning full-stack development, backend systems, DevOps/cloud, AI, industrial computer vision, architecture, and production operations. Initial language difficulty is approximately A2–B1.

The initial product is private and single-user in access, but **not** single-user in its core domain design. Tables and services retain explicit learner ownership so later multi-user support does not require re-modeling progress.

## 4. Primary job to be done

> When I prepare for a German software interview, help me practice the exact language and explanations I need, remember what I repeatedly get wrong, and progressively remove assistance until I can answer naturally on my own.

## 5. Product promise

In 21 disciplined days, the learner will improve their ability to:

- give a 60–90 second introduction;
- explain at least three real projects at multiple depths;
- state individual responsibilities and measurable outcomes;
- discuss technologies and trade-offs;
- explain a difficult incident using a clear story;
- answer core HR and behavioral questions;
- handle technical follow-ups;
- ask professional questions at the end;
- understand and repair recurring language errors.

The product promises structured practice and measurable improvement, not employment or a particular CEFR certification.

## 6. Learning principles

### Active production over passive recognition
Recognition is useful early, but mastery requires recall, sentence construction, and speech.

### Context before isolated memorization
A verb is learned with conjugation, grammar behavior, interview contexts, examples, collocations, and linked questions.

### Progressive removal of support
A concept moves through recognition, controlled production, free production, and interview transfer.

### Short feedback loops
Feedback must explain the highest-value correction without overwhelming the learner.

### Real experience over invented biography
Personalized answers must remain truthful. AI may improve language and structure but must not fabricate experience.

### Retrieval scheduling
Review timing uses performance evidence, not a fixed “repeat every lesson” schedule.

### Explainability
Readiness scores and corrections must show why a result was produced.

## 7. Experience principles

- Mobile-first and usable in 10–20 minute blocks.
- A daily session has a clear beginning, target, and completion state.
- Long speaking tasks may be completed separately.
- The learner can always inspect the underlying rule and example.
- Failure is framed as information for scheduling, not punishment.
- Gamification supports consistency but does not block study.
- No artificial hearts system prevents practice.
- The interface may be bilingual where helpful; German exposure increases over time.
- Accessibility and keyboard operation are designed, not retrofitted.

## 8. Product horizons

### Horizon 1: Private personal coach
One learner, one Software Developer track, one 21-day plan, editorial tools, progress, review, text exercises, speech, and mock interviews.

### Horizon 2: Multi-user professional product
Account onboarding, CV-derived personalization, multiple technical tracks, subscriptions, privacy controls, and robust operations.

### Horizon 3: Extensible career-language platform
Multiple professions, destination languages, organizations, instructors, course marketplaces, certification-style assessments, and provider-neutral intelligence.

Horizons guide architecture; they do not expand the MVP scope.

## 9. Explicit non-goals for initial releases

- teaching complete general German;
- replacing a language teacher or certified assessment;
- native mobile applications;
- live human tutoring marketplace;
- public social feed;
- enterprise tenancy;
- real-time multiplayer;
- fully autonomous AI publishing;
- microservice decomposition without proven need;
- complex payment and subscription workflows;
- supporting every exercise format immediately.

## 10. Success measures

### Learning outcomes
- proportion of assigned concepts reaching stable mastery;
- improvement between baseline and final mock interview;
- reduction in repeated grammar and vocabulary errors;
- number of independent, relevant spoken answers;
- retention after 1, 3, 7, and 14 days.

### Engagement
- daily plan completion;
- streak continuity without coercion;
- speaking minutes;
- review completion rate;
- lesson abandonment points.

### Product quality
- content publishing lead time;
- percentage of new content added without code changes;
- deterministic exercise evaluation accuracy;
- AI evaluation agreement on benchmark responses;
- crash-free sessions and API reliability.

## 11. North-star metric

**Independent interview-ready answers per week**

An answer qualifies when it is completed without scaffolding, addresses the question, remains truthful, and meets minimum thresholds for comprehensibility, structure, grammar, and job relevance.

## 12. Product guardrails

- Never invent credentials, employers, projects, or results.
- Never present AI feedback as an objective language certificate.
- Never make irreversible schema choices around a single course or language.
- Never bind progress to mutable UI ordering.
- Never expose private CV or voice data by default.
- Never allow a provider outage to erase completed learning work.
