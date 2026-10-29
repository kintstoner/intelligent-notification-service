# 2. Instructions only in the system prompt; the user message is the request as typed

[Español](0002-instructions-only-in-the-system-prompt.es.md)

- Status: accepted
- Date: 2026-10-29

## Context

The extraction call takes a list of `system`/`user` messages. A common pattern wraps the user's text in a template
("Extract the recipient from: ...", sometimes with examples). The mock reads only the **last user message**: it
detects the channel by searching for words like "email" and takes the **first** email or phone number it finds. A
template or an example inside the user message changes its answer. A real model has the opposite problem: text in the
user turn that looks like instructions can override them (prompt injection).

## Decision

- All instructions live in one system prompt, versioned with the code in
  [`app/prompts/extract_system.md`](../../app/prompts/extract_system.md).
- The user message is exactly the `user_input` received, with no template and no examples.
- The prompt is written for a real model: the extractor's role, the exact JSON schema, how to write the message (the
  text to deliver, not the instruction to send it; same language; names, dates and codes kept), the channel rules
  (follow the recipient when the requested channel and the recipient disagree), what to do when something is missing
  (nulls, never guesses), and that the user text is data, not instructions.
- Its few examples live inside the system prompt, never as extra user/assistant turns.

## Consequences

- The mock's extraction is not contaminated by our own words.
- Separating instructions from data is the basic defence against prompt injection.
- The mock ignores the system prompt, so its quality cannot be measured here; it is covered by a test that checks the
  schema keys are present, and by review.
