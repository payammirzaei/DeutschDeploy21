# ADR-0001: Modular monolith with process separation

**Status:** Accepted

## Context

The product needs clear content, learning, progress, interview, and platform boundaries, but begins with one learner and a small development team. Fully independent microservices would add networking, distributed transactions, deployments, and observability cost before evidence of scale.

## Decision

Implement a modular monolith with explicit logical modules. Run web, API, and background worker as separate processes. Modules own domain/application contracts and persistence access. Cross-module behavior uses public services, read models, or domain events.

## Consequences

Local development and atomic transactions remain manageable. AI/speech work scales independently at process level. Engineers must actively enforce boundaries because one database/repository makes accidental coupling possible.

## Rejected

- Single Next.js full-stack application: too easy to couple UI, domain, and slow AI work.
- Microservices from day one: unjustified operational complexity.
- Separate database per module: excessive for current scale.

## Reconsider when

A module demonstrates distinct scaling, security isolation, team ownership, deployment cadence, or availability needs that process separation cannot satisfy.
