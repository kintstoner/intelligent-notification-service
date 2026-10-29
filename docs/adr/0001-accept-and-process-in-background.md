# 1. Accept with 202 and process in background workers

[Español](0001-accept-and-process-in-background.es.md)

- Status: accepted
- Date: 2026-10-29

## Context

Processing a request means one or two AI calls of 1.5 to 3 s each, then a notification call. The scorecard wants a
mean `/process` latency under 400 ms and counts any 4xx/5xx returned to k6 as unavailability. Under load, k6 sends
up to ~130 `/process` calls per second.

## Options

1. Process inside the HTTP request: `/process` takes seconds, and slows down further under load.
2. Accept the request, put it in a queue and process it in background workers.

## Decision

Option 2. `/process` validates that the request exists, enqueues it and answers `202 Accepted` with its current
status. A fixed number of asyncio workers (`WORKERS`, default 100) drain the queue, started and stopped with the
application's lifespan.

- Idempotent: a request already queued, processing or finished is not enqueued again; the call just returns its
  status. An unknown id is a 404 (a client error, not saturation).
- The queue is bounded (`QUEUE_MAX_SIZE`, default 10,000) to protect memory. When it is full, `/process` still
  answers 202, the request stays `queued` with `reason: queue_full`, and calling `/process` again retries it. Internal
  saturation never becomes an error for the caller.
- A bug while processing one request marks it `failed` with `reason: internal_error`; the worker carries on.

## Consequences

- `/process` answers in under a millisecond whatever the AI or the provider do (k6 mean: 0.66 ms).
- Every endpoint is `async`: a sync endpoint would run in FastAPI's thread pool and touch the asyncio queues from
  another thread.
- The status endpoint is how callers learn the outcome; `reason` (an extra, optional field) says why a request failed
  or is still waiting.
- State lives in memory: see ADR 7.
