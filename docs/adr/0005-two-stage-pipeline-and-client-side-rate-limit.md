# 5. Two-stage pipeline with a client-side rate limit for notifications

[Español](0005-two-stage-pipeline-and-client-side-rate-limit.es.md)

- Status: accepted (pacing revised the same day, see "History")
- Date: 2026-10-29

## Context

Read from `provider/app.py`: `/v1/notify` accepts **50 calls in any sliding 10-second window** and answers 429
beyond that; it may also return 500 (probability 0 in the code, but documented). The load test creates about 70
requests per second on average. Delivering everything during the test is impossible: the system has to degrade in an
orderly way.

If the AI workers called the provider themselves, each would wait for its turn: within seconds every worker would be
stuck behind the rate limit and extraction would stop.

## Options for pacing

1. Send as fast as possible and retry on 429: most calls are rejected, retries pile up.
2. Space calls evenly at a rate below the limit (one every 0.22 s at 4.5/s).
3. Apply the provider's own rule on our side: at most N calls in any sliding 10 s window, with N below 50.

## Decision

- **Two stages**: the AI workers turn requests into validated notifications and hand them to a delivery queue; a few
  delivery workers (`NOTIFY_CONCURRENCY`, default 10) send them. Delivery sets the final status.
- **Pacing (option 3)**: every notify attempt waits for room in a sliding-window limiter of
  `NOTIFY_WINDOW_MAX_CALLS` (45) calls per `NOTIFY_WINDOW_S` (10 s). While the window has room a call goes out at
  once; when it is full, the next call waits for the oldest one to leave the window. 45 instead of 50 leaves room for
  the variation between a call leaving the service and reaching the provider.
- **Retries**: 429, 5xx and timeouts are retried with exponential backoff and full jitter (0.5 s, doubling), up to
  `NOTIFY_MAX_ATTEMPTS` (3) attempts, each one through the limiter. `Retry-After` is honoured if the provider ever
  sends it. Other 4xx are not retried (`provider_rejected`); exhausted retries end as `rate_limited` or
  `provider_error`.
- **Backlog**: notifications wait for their turn and are delivered in order; none is dropped for being late. The
  delivery queue is bounded too (`delivery_backlog_full` beyond `QUEUE_MAX_SIZE`).

## History

The first version used option 2. Testing by hand showed its cost: 30 requests sent at once had a median of 5.3 s
and a maximum of 8.5 s to reach `sent`, almost all of it waiting for an evenly spaced slot, although the provider
would have taken all 30 at once. With the sliding window the same 30 requests have a median of 2.8 s, which is the
AI's own latency. Under sustained load both deliver at the same average rate.

## Consequences

- Official load test: every notification that passed validation was delivered (2,725), all on the first attempt,
  with **no 429s**. (With option 2, one run had 5 429s, all delivered on retry.)
- A quiet service sends without delay; a burst of up to 45 notifications goes out at once.
- After a long burst, the backlog drains at 4.5/s on average: the ~2,300 notifications left when extraction caught up
  took about 9 minutes. Requests show `processing` meanwhile, and `/health` reports both backlogs.
- With several instances the limit would have to be shared (for example a Redis-based limiter), since the provider's
  quota is global.
- For notifications that lose their value when late (one-time codes), a maximum age per notification would be the
  next step.
