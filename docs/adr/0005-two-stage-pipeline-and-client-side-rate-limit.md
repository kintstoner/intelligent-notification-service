# 5. Two-stage pipeline with a client-side rate limit for notifications

[Español](0005-two-stage-pipeline-and-client-side-rate-limit.es.md)

- Status: accepted
- Date: 2026-10-29

## Context

Read from `provider/app.py`: `/v1/notify` accepts **50 calls in any sliding 10-second window** (5 per second) and
answers 429 beyond that; it may also return 500 (probability 0 in the code, but documented). The load test creates
about 70 requests per second on average. Delivering everything during the test is impossible: the system has to
degrade in an orderly way.

If the AI workers called the provider themselves, each would wait for its turn: within seconds every worker would be
stuck behind the rate limit and extraction would stop.

## Options for pacing

1. Send as fast as possible and retry on 429: most calls are rejected, retries pile up.
2. A token bucket that allows bursts: a burst plus a steady 4.5/s can still exceed 50 in a sliding window.
3. Evenly spaced calls at a rate below the limit, no bursts.

## Decision

- **Two stages**: the AI workers turn requests into validated notifications and hand them to a delivery queue; a few
  delivery workers (`NOTIFY_CONCURRENCY`, default 10) send them. Delivery sets the final status.
- **Pacing (option 3)**: every notify attempt waits for a slot of a rate limiter that spaces calls evenly at
  `NOTIFY_RATE_PER_S` (default 4.5/s): at most 46 calls in any 10 s window, under the provider's 50.
- **Retries**: 429, 5xx and timeouts are retried with exponential backoff and full jitter (0.5 s, doubling), up to
  `NOTIFY_MAX_ATTEMPTS` (3) attempts, each one through the rate limiter. `Retry-After` is honoured if the provider ever
  sends it. Other 4xx are not retried (`provider_rejected`); exhausted retries end as `rate_limited` or
  `provider_error`.
- **Backlog**: notifications wait for their turn and are delivered in order; none is dropped for being late. The
  delivery queue is bounded too (`delivery_backlog_full` beyond `QUEUE_MAX_SIZE`).

## Consequences

- Every notification that passed validation was delivered (2,721). The provider answered 429 to 5 of 2,726 calls,
  all right after the test while the AI workers were clearing their backlog: the limiter spaces calls when they
  leave, and under that event-loop load their arrival at the provider varies enough to put a few windows over 50.
  The retries delivered all 5; a lower rate gives more margin.
- After a burst, the backlog drains at 4.5/s: the ~2,200 notifications left at the end of the 40 s test took about
  8 minutes. Requests show `processing` meanwhile, and `/health` reports both backlogs.
- With several instances the limit would have to be shared (for example a Redis-based limiter), since the provider's
  quota is global.
- For notifications that lose their value when late (one-time codes), a maximum age per notification would be the
  next step.
