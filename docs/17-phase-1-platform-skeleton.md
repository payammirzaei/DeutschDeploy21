# Phase 1 platform skeleton

**Status:** Implemented baseline; CI and Railway staging verification pending.

## Delivered

- monorepo layout with `apps/web`, `apps/api`, and a shared API-contract package;
- Next.js 16.3.3 mobile-first PWA shell;
- FastAPI 0.141.1 API with versioned `/api/v1` routes;
- PostgreSQL identity and durable platform-job tables with Alembic migration;
- Redis-assisted background worker with PostgreSQL fallback discovery;
- private bootstrap authentication using Argon2 password hashes and an HttpOnly session cookie;
- liveness/readiness endpoints;
- OpenAPI export plus TypeScript generation pipeline;
- Docker Compose development topology;
- Railway service configuration;
- CI for Python lint/tests and frontend lint/types/build;
- correlation IDs and structured API/worker logging.

## End-to-end proof path

```text
Browser
  → Next.js same-origin /api rewrite
  → authenticated FastAPI request
  → PostgreSQL platform_jobs insert
  → Redis queue signal
  → worker claims durable job
  → PostgreSQL result update
  → browser polls and renders succeeded result
```

The job idempotency key has a database uniqueness constraint. Redis is not authoritative: a queued job remains discoverable from PostgreSQL if the queue signal is lost.

## Authentication scope

Phase 1 deliberately implements private single-user bootstrap rather than public registration. Credentials are environment variables and passwords are stored only as Argon2 hashes. Production/staging configuration rejects missing bootstrap credentials and known development-only passwords.

## PWA scope

The web app has an installable manifest and service worker. The service worker never caches `/api/*`. Offline learning-attempt semantics remain a later phase because they require the attempt/idempotency model from Phase 3.

## Remaining verification / debt

- run CI on the pull request;
- provision Railway staging resources and verify login → DB → Redis → worker → DB;
- generate and commit dependency lockfiles once the dependency resolver is available (the current execution environment cannot reach npm/PyPI);
- capture migration/deployment rollback notes after first staging deployment.

No Phase 2 content tables are introduced here. Content and curriculum remain intentionally separate from platform scaffolding.
