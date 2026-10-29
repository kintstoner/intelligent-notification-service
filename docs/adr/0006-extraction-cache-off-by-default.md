# 6. Extraction cache available but off by default

[Español](0006-extraction-cache-off-by-default.es.md)

- Status: accepted
- Date: 2026-10-29

## Context

The load test repeats four sentences. Caching extractions by identical `user_input` would bring the AI call ratio
close to zero, which says nothing about how the service handles a real model and would read as gaming the scorecard.

## Decision

The cache exists behind `EXTRACTION_CACHE_ENABLED`, default `false`. When enabled, a successful extraction is reused
for an identical request text; failures are never cached.

## Consequences

- The scorecard shows the real cost of extraction (ratio 1.10).
- In production it makes sense as deduplication: the same request submitted twice (a retrying client, a double
  click) should not pay for a second extraction. It would then need a size bound and a TTL; the current dict is
  unbounded and lives in memory.
