# 3. Guardrails and a deterministic fallback; the message is never invented

[Español](0003-guardrails-and-deterministic-fallback.es.md)

- Status: accepted
- Date: 2026-10-29

## Context

Read from `provider/responses.py`: half of the AI answers are clean JSON. The rest have renamed keys
(`Recipient/body/channel`, `To/Message/Type`, `destination/text/method`), extra fields, a missing `type` or `to`,
Markdown fences, JSON inside a sentence, output cut short, single quotes, unquoted keys, or a refusal in plain text.

## Decision

Three steps, each a set of pure functions:

1. **Guardrails** ([`guardrails.py`](../../app/services/guardrails.py)): strip fences; find the first balanced
   `{...}`, skipping braces inside strings; parse it with `json.loads`, then `ast.literal_eval` (single quotes,
   apostrophes inside values included), then with quoted keys; close an object cut after its last value; map key
   synonyms case-insensitively and drop unknown keys; normalise the type (`mail`, `correo` → email; `phone` → sms).
   No JSON at all is a refusal, classified as *policy* or *missing information*.
2. **Fallback** ([`fallback_extractor.py`](../../app/services/fallback_extractor.py)): a missing recipient or
   channel is recovered from the original request with regular expressions (first email, else first phone number;
   channel from the recipient's form, then from keywords).
3. **Validation** (`Notification`, Pydantic): the recipient must match the channel (an email address for email, a
   phone number for SMS), the message must not be blank; phone numbers are sent as digits.

The message is never filled in by the fallback. If the AI gives no message, the request is retried once (ADR 4) and
then fails with `missing_message`.

## Consequences

- Every one of the mock's 16 answer shapes is handled; the tests run the provider's own generator through each
  branch, so they follow the mock's code rather than a copy of it.
- Sending a notification with made-up content is worse than not sending it, so some requests fail on purpose, with a
  reason.
- The unquoted-key repair is a regular expression applied only when strict parsing fails; a message containing
  `, word:` could in theory be altered by it.
