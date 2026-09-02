# DeutschDeploy21

> **Speak German. Explain Your Work. Get Hired.**

DeutschDeploy21 is a focused, mobile-first learning platform for software professionals preparing for German job interviews. It combines a structured 21-day curriculum, active recall, spaced repetition, speaking practice, and realistic HR and technical mock interviews.

The first release is personalized for one learner and the Software Developer track (German A2–B1), while the domain model is designed to later support multiple users, professions, languages, course lengths, and AI or speech providers without rewriting the learning core.

## Product outcome

After 21 days, the learner should be able to:

- introduce themselves naturally in German;
- explain experience, responsibilities, projects, architecture, and technical decisions;
- narrate problems and solutions with appropriate language;
- answer essential HR, behavioral, backend, frontend, DevOps, cloud, AI, and computer-vision questions;
- recover when a question is unclear;
- complete a realistic German interview and understand remaining weaknesses.

DeutschDeploy21 does **not** attempt to teach all German. It optimizes for a concrete performance outcome: a credible, understandable, job-relevant interview.

## Architecture direction

- **Web/PWA:** Next.js + TypeScript
- **API:** FastAPI
- **Database:** PostgreSQL
- **Queue/cache:** Redis
- **Async work:** background worker
- **Media:** S3-compatible object storage behind an adapter
- **Deployment:** Docker services on Railway
- **AI and speech:** provider-neutral gateways

The implementation begins as a modular monolith with separate web, API, and worker processes. Microservices are not required until operational evidence justifies them.

## Non-negotiable principles

1. Learning content is data, never hard-coded page logic.
2. Curriculum placement is separate from reusable content.
3. Exercise rendering, generation, and evaluation are separate.
4. Published content is versioned; edits never silently invalidate history.
5. Progress references immutable learning targets, not screen positions.
6. AI may propose or evaluate, but canonical content remains reviewable.
7. External providers are replaceable through ports and adapters.
8. Railway is the deployment target, not a domain dependency.
9. Accessibility, mobile usability, observability, testing, and safe migrations are release requirements.
10. Private-user scope may simplify features but never corrupt the long-term data model.

## Documentation

The [documentation index](docs/README.md) contains the full product and engineering baseline:

- product vision and requirements;
- system architecture and domain model;
- content authoring and versioning;
- 21-day curriculum;
- extensible exercise engine;
- mastery and spaced repetition;
- AI, speech, and mock interviews;
- Railway operations;
- security, privacy, testing, and quality;
- roadmap, development rules, UX, glossary, and ADRs.

## Current status

**Phase 0 — Product and architecture foundation**

Application scaffolding begins after the Phase 0 baseline is reviewed for contradictions and the foundational decisions are accepted.

## Working agreement

Documentation is part of the product. Any change that alters domain meaning, contracts, persistence, content lifecycle, evaluation, security posture, or deployment topology must update the relevant document or create an Architecture Decision Record.
