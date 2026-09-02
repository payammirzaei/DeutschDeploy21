# ADR-0003: PostgreSQL as source of truth

**Status:** Accepted

## Context

Content relationships, releases, attempts, ownership, and mastery need strong integrity. Redis and provider services are operational dependencies and may lose or change data.

## Decision

PostgreSQL owns all durable product truth. Redis is queue/cache/lock infrastructure only. Object storage owns media bytes while PostgreSQL owns media identity, state, ownership, checksum, and retention. AI providers never own the canonical result history.

## Consequences

Transactions and constraints protect important state. Queue recovery requires an outbox and durable job metadata. Database schema/migration quality becomes critical.

## Rejected

- Redis as durable progress store.
- JSON files as the live content database.
- Provider dashboards as evaluation history.
- Store audio bytes directly in ordinary relational rows.

## Reconsider when

A demonstrated workload needs a specialized store; PostgreSQL remains the system of record or receives a documented synchronization/ownership decision.
