# ADR-0002: Railway-first portable platform

**Status:** Accepted

## Context

The preferred hosting platform is Railway. The product should gain simple Git-based container deployment without becoming impossible to migrate.

## Decision

Deploy containerized web, API, worker, PostgreSQL, Redis, and object-storage integration through Railway. Domain code depends only on standard ports and protocols. Railway configuration remains under infrastructure composition.

## Consequences

Operations stay compact and consistent. Railway features may be used at the deployment layer. Portability requires maintained Dockerfiles, standard backups, externalized configuration, and avoidance of Railway-specific domain assumptions.

## Rejected

- Supabase platform dependency.
- Premature AWS multi-service topology.
- Unmanaged single VPS as the only target.

## Reconsider when

Cost, regional requirements, reliability, compliance, or required platform capabilities materially exceed Railway’s fit.
