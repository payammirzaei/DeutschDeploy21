# Phase 8C — Release hardening

**Status:** In progress

## Outcome

Close the remaining pre-staging risks without changing learning semantics.

## Security and PWA hardening

The service worker no longer caches authenticated documents or arbitrary same-origin GET responses. It caches only explicitly public application assets and immutable Next.js static assets. Learning attempt durability continues to come from the IndexedDB outbox; the browser must never use cached authenticated HTML as a substitute for server authorization.

## Accessibility hardening

- global keyboard skip link with a stable main-content target;
- visible focus treatment remains global;
- reduced-motion preference remains respected;
- choice exercises use native button semantics with `aria-pressed` instead of incomplete custom radio behavior;
- grouped puzzle/matching controls expose group semantics;
- language metadata is applied to German answer fields and German/Persian matching content;
- decorative option letters and language marks are hidden from assistive technology.

## Performance notes

The release keeps the current client architecture intentionally small: no additional UI framework, animation package, analytics bundle or gamification runtime was added. Static PWA caching is constrained to safe assets rather than broad runtime HTML caching.

## Staging gate

Before Phase 8 is marked complete:

1. CI migration, Python lint/tests and OpenAPI export pass;
2. web ESLint, TypeScript and production build pass;
3. staging deploy uses a separate Railway project/environment and database;
4. health/readiness and worker round-trip smoke tests pass;
5. authenticated learning, one offline attempt replay and one review flow are exercised;
6. operational summary reports no queue/provider alert after the smoke run.

## Non-goals

- no new learning features;
- no persistence changes;
- no production deployment before staging verification;
- no claim of a formal WCAG certification from code review alone.
