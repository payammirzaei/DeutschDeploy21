# Phase 8C — Release hardening

**Status:** Complete — 2026-09-02

## Outcome

The remaining pre-staging risks were closed without changing learning semantics. Phase 8C produced repeatable CI and Railway evidence for the deployment artifacts, private worker path, authenticated learning flow, offline-safe attempt replay, review flow, and operational visibility.

## Security and PWA hardening

The service worker no longer caches authenticated documents or arbitrary same-origin GET responses. It caches only explicitly public application assets and immutable Next.js static assets. Learning attempt durability continues to come from the IndexedDB outbox; the browser never uses cached authenticated HTML as a substitute for server authorization.

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

## Staging gate — completed

1. **CI / API:** migrations, Python lint/tests and OpenAPI export pass.
2. **CI / Web:** ESLint, TypeScript, the IndexedDB offline-attempt replay test and the production Next.js build pass.
3. **Deployment artifacts:** CI builds the API, dedicated worker and Web Docker images; the packaged API import and packaged worker startup smoke checks pass.
4. **Isolated staging evidence:** `DeutschDeploy21-staging` was used as a separate Railway project for the Phase 8C validation run with PostgreSQL, Redis, API, Web and worker services. Those staging services were later removed intentionally, so this section records historical release evidence rather than claiming a currently active Railway topology.
5. **Runtime contract:** the API listens on the explicit internal port `8000`; Web and release-smoke traffic used the same private-network API contract during the validation run.
6. **Worker:** the dedicated worker image started on Railway and emitted `worker_started` for queue `dd21:jobs`.
7. **Authenticated learning:** the Railway release-smoke performed login, readiness, a real worker echo round-trip, learning start and a graded learning attempt.
8. **Idempotent/offline safety:** the staging smoke submitted the same attempt twice with one idempotency key and received the same attempt/evaluation; CI separately simulates a browser network interruption with fake IndexedDB and verifies replay preserves the original idempotency key and drains the outbox.
9. **Review:** the smoke created mastery evidence, forced the target due, received a real review activity and submitted the review attempt successfully.
10. **Operations:** the final smoke required the operational summary to report `status=ok` with no alert codes.
11. **Repeatability/cleanup:** release-smoke transfers any global starter-content ownership accidentally created by disposable smoke identities to the configured bootstrap user, removes stale `release-smoke-*` users, and deletes the current smoke user after the run. The final Railway run reported `stale_smoke_users_cleaned: 1` and `smoke_user_cleaned: True`.

The final Railway evidence was:

```text
RELEASE_SMOKE_OK {
  'stale_smoke_users_cleaned': 1,
  'readiness': 'ok',
  'worker_round_trip': 'ok',
  'attempt_replay': 'idempotent',
  'review_flow': 'ok',
  'operations': 'ok',
  'smoke_user_cleaned': True
}
```

The cleanup fix was validated by CI before merge; the release-smoke completed successfully on Railway during the Phase 8C validation window.

## Remaining release boundary

Phase 8C completes the private core-product release-hardening gate. It does **not** claim that production speech infrastructure is configured: the staging core-platform smoke intentionally used test-mode speech/storage policy. A real production speech release still requires production object storage and a real transcription provider/credentials.

Phase 9 public-product work remains explicitly inactive until chosen; public registration, billing, recovery, abuse prevention and other multi-user SaaS concerns are not required for the current private product.

## Non-goals

- no new learning features;
- no formal WCAG certification claim;
- no claim that production speech provider/storage is configured;
- no automatic activation of Phase 9 public-product scope.
