# 4. At most one AI retry, and only when it can help

[Español](0004-at-most-one-ai-retry.es.md)

- Status: accepted
- Date: 2026-10-29

## Context

The scorecard divides AI calls by `/process` calls: green below 1.5, red from 2.5. Retrying until the model returns
clean JSON would push that ratio up, and it is unnecessary: the guardrails repair dirty JSON (ADR 3). Some failures
are worth one more call, though: a policy refusal (random in the mock), a network error, an answer with no message.

## Decision

At most `1 + AI_MAX_RETRIES` calls per request (default 2). A second call is made only for:

| First call | Retry? | Reason if it still fails |
|---|---|---|
| Timeout, transport error, 5xx | Yes | `ai_unavailable` |
| Policy refusal (no JSON) | Yes | `ai_refused` |
| Object that cannot be read even after the repairs | Yes | `ai_output_unreadable` |
| Valid object without a message | Yes | `missing_message` |
| "Unable to identify the destination/type" | No: the same input gets the same answer | `missing_information` |
| 4xx from the AI engine (bad key), envelope without choices | No | `ai_unavailable` |
| Recipient does not match the channel after the fallback | No | `invalid_notification` |
| Dirty JSON (fences, renamed keys, single quotes...) | Never: the guardrails fix it | |

## Consequences

- Measured ratio in the official load test: **1.10** (3,014 AI calls for 2,749 `/process` calls).
- About 10 % of answers are refusals; one retry turns most of them into sent notifications.
- Refusals are told apart by their wording, which is a heuristic: an unusual "missing information" text would be
  retried once, wasting one call.
