# API and worker

FastAPI owns synchronous application use cases and PostgreSQL state. The worker owns asynchronous jobs. Redis is transport/coordination only; `platform_jobs` remains durable in PostgreSQL.

## Local

From the repository root:

```bash
make bootstrap
make migrate
make api-dev
make worker-dev
```

The private bootstrap user is created from `APP_BOOTSTRAP_EMAIL` and `APP_BOOTSTRAP_PASSWORD` on API startup.
