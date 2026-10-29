# Design decisions

[Español](DECISIONS.es.md)

One line per decision; the full reasoning is in each Architecture Decision Record.

| # | Decision | Why, in one line |
|---|---|---|
| [1](adr/0001-accept-and-process-in-background.md) | `/process` enqueues and answers 202; asyncio workers do the work; a full queue is never an error | The AI takes seconds; the caller must not wait for it or see internal saturation |
| [2](adr/0002-instructions-only-in-the-system-prompt.md) | Instructions only in a versioned system prompt; the user message is the raw request | Our words would contaminate the mock's extraction, and mixing instructions with data invites prompt injection |
| [3](adr/0003-guardrails-and-deterministic-fallback.md) | Guardrails repair the AI's output; a regex fallback recovers recipient and channel; the message is never invented | Every noisy answer becomes usable without a new call, and nothing nobody wrote is sent |
| [4](adr/0004-at-most-one-ai-retry.md) | At most one AI retry, only for refusals, cut answers, missing messages and network errors | Dirty JSON is fixed, not retried; ratio 1.10 |
| [5](adr/0005-two-stage-pipeline-and-client-side-rate-limit.md) | Delivery is a second queue paced at 4.5/s, evenly spaced, with bounded retries | The provider allows 50 per 10 s; AI workers never wait behind that limit, and 429s stay rare (5 of 2,726) and are retried |
| [6](adr/0006-extraction-cache-off-by-default.md) | Extraction cache behind a flag, off | With four repeated sentences it would hide the real cost of extraction |
| [7](adr/0007-in-memory-state-behind-an-interface.md) | In-memory state behind a repository protocol | One process, no database in the challenge; a shared store fits behind the same protocol |
