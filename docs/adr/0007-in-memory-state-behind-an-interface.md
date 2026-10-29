# 7. In-memory state behind a repository interface

[Español](0007-in-memory-state-behind-an-interface.es.md)

- Status: accepted
- Date: 2026-10-29

## Context

The challenge runs a single container with the given Dockerfile (`uvicorn main:app`, one process) and no database.

## Decision

Requests are kept in a dict behind a `RequestRepository` protocol. No lock: every access runs on the single event
loop and none of them awaits, so a lock would be dead code. The queues are `asyncio.Queue`s in the same process.

## Consequences

- Simple and fast; nothing to install.
- A restart loses requests, including those queued or waiting for delivery. Several uvicorn workers would each have
  their own state.
- The next step for production: a shared store (Postgres or Redis) implementing the same protocol, and a durable
  queue (Redis streams, SQS, Kafka) in place of the in-process queues. The processing steps would not change.
