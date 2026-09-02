# Platform, Docker, and Railway

**Status:** Accepted baseline  
**Strategy:** Railway-first, portable by standards

## 1. Principle

Railway hosts the product. Railway-specific assumptions do not enter domain logic. Services depend on PostgreSQL, Redis, S3-compatible storage, HTTP, and standard container behavior so migration remains feasible.

## 2. Repository target

```text
DeutschDeploy21/
├── apps/
│   ├── web/          # Next.js PWA
│   ├── api/          # FastAPI HTTP/application composition
│   └── worker/       # async job consumers and scheduled tasks
├── packages/
│   ├── contracts/    # OpenAPI-generated/shared contracts
│   ├── content-schema/
│   ├── exercise-contracts/
│   ├── ui/
│   └── config/
├── infrastructure/
│   ├── docker/
│   ├── railway/
│   └── scripts/
├── docs/
└── tests/
```

Actual scaffold may adjust language-workspace details through an ADR.

## 3. Railway services

### web
Next.js server and static/PWA assets. Public HTTPS domain. Calls API through configured origin.

### api
FastAPI, authentication, application use cases, OpenAPI, health endpoints, database transaction ownership, and job enqueue/outbox.

### worker
Speech, AI, media, reports, and outbox delivery. Starts with one process and named queues; scale by queue evidence.

### postgres
Primary durable database with backups and restricted credentials.

### redis
Queue/locks/rate limits/ephemeral cache. No unique durable learning state.

### object storage
Railway bucket if suitable, otherwise S3-compatible service. Always behind adapter and explicit metadata.

Scheduler may initially run as a worker mode with distributed lock. Separate service only when operationally justified.

## 4. Environments

- **local:** Docker Compose and local provider fakes.
- **preview:** per-PR where affordable; isolated app and safe data.
- **staging:** production-like integration and migration validation.
- **production:** private active learner and real providers.

Secrets and databases never cross environments. Seed content is explicit and idempotent.

## 5. Configuration

Use environment variables validated at startup. Maintain `.env.example` without secrets. Group settings by database, Redis, storage, auth, providers, observability, retention, and feature activation.

Application refuses startup for invalid security-critical configuration. Nonessential provider absence marks the feature unavailable rather than crashing core learning.

## 6. Containers

- multi-stage builds;
- pinned runtime major/minor;
- non-root user;
- minimal image;
- deterministic dependency lockfiles;
- read-only filesystem where practical;
- explicit health checks;
- graceful shutdown;
- no secrets baked into layers;
- migrations not run concurrently by every replica.

## 7. Health endpoints

- `/health/live`: process responsive, no dependency query.
- `/health/ready`: required dependencies usable.
- `/health/details`: authenticated operational detail.
- worker heartbeat and queue age metrics.

Readiness should not fail because an optional AI provider is temporarily unavailable.

## 8. Deployment flow

1. pull request checks;
2. build immutable artifacts;
3. run unit/contract/security checks;
4. validate migrations against representative database;
5. deploy compatible code;
6. execute migration through one controlled job;
7. verify health and smoke tests;
8. monitor errors, latency, and queue;
9. promote/complete;
10. rollback application or apply corrective migration if required.

## 9. Database operations

Enable automated backups and perform restore drills. Use connection pooling appropriate to Railway/PostgreSQL limits. Observe connection count, storage, slow queries, locks, replica needs, and migration duration.

Schema migrations are not coupled blindly to web startup.

## 10. Queues

Initial queues may be `critical`, `speech`, `ai`, `media`, and `maintenance`. Jobs have idempotency, deadlines, retry policy, visibility timeout, and dead-letter status.

Worker concurrency is limited to database and provider capacity, not maximum CPU alone.

## 11. Storage

Browser uploads use short-lived signed URLs. Metadata is created before upload and finalized after checksum/size verification. Object keys are opaque, user-scoped, and non-public. Lifecycle rules remove expired media.

Never use ephemeral container disk for durable recording storage.

## 12. Domains and networking

Use separate origins or a controlled same-site setup. Enforce HTTPS, exact CORS origins, secure cookies, trusted proxy configuration, rate limits, and internal service access where supported.

## 13. Observability

Structured JSON logs, request/job correlation IDs, error tracking, latency histograms, queue depth/oldest age, database metrics, provider success/latency/cost, storage failures, and deployment markers.

Alerts initially cover application down, database exhaustion, migration failure, queue stuck, high provider failure, and backup failure.

## 14. Cost controls

Set Railway resource budgets, provider usage limits, maximum audio duration/size, queue concurrency, retention, and alerts. Prefer scaling from measurement. Preview environments may sleep or be short-lived.

## 15. Portability checklist

A migration away from Railway should require infrastructure configuration, not domain rewrite. Verify standards-based database migrations, Redis protocol, S3 port, Dockerfiles, externalized config, exportable backups, and provider-neutral URLs.

## 16. Disaster recovery

Document and test:

- PostgreSQL restore;
- object metadata reconciliation;
- Redis loss recovery from outbox/database;
- secret rotation;
- provider outage fallback;
- erroneous deployment rollback;
- accidental content release supersession.

Target RPO/RTO will be selected after measuring business need; until then, no untested recovery claim is made.
