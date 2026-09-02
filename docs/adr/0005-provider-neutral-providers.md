# ADR-0005: Provider-neutral AI, speech, and storage

**Status:** Accepted

## Context

AI, transcription, pronunciation, and object-storage vendors vary in quality, cost, privacy, availability, and interfaces. Direct SDK usage throughout business code creates lock-in.

## Decision

Application-owned ports define provider-neutral requests/results. Adapters contain SDK and provider-specific behavior. Invocation metadata records provider/model/version/cost. Core text learning degrades gracefully without optional providers.

## Consequences

Adapters and conformance tests require additional discipline. Not every provider capability will fit the common contract; optional capability discovery is explicit. Swapping providers avoids domain rewrite.

## Rejected

- Provider SDK objects in domain models.
- One global AI helper used from arbitrary modules.
- Treating raw provider response as authoritative evaluation.
- Storing durable media only on container disk.

## Reconsider when

A strategically essential provider feature cannot be represented without harmful lowest-common-denominator design; add a capability-specific port rather than leaking the SDK globally.
