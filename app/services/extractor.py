from pathlib import Path

import httpx

# Versioned with the code: a prompt change is reviewed and tested like any other change
SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "extract_system.md").read_text(encoding="utf-8")


class ExtractionError(Exception):
    """The AI engine gave no usable answer. Retryable when asking again could succeed (timeouts, 5xx)."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class Extractor:
    """Client for the AI extraction endpoint. Returns the model's raw text; the guardrails make sense of it."""

    def __init__(self, client: httpx.AsyncClient, timeout_s: float) -> None:
        self._client = client
        self._timeout_s = timeout_s

    async def extract(self, user_input: str) -> str:
        # Instructions go only in the system message and the user message is the request as typed: mixing them would
        # let the request's text be read as instructions (prompt injection)
        payload = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ]
        }
        try:
            response = await self._client.post("/v1/ai/extract", json=payload, timeout=self._timeout_s)
        except httpx.TransportError as error:
            raise ExtractionError(f"AI engine unreachable: {error!r}", retryable=True) from error

        if response.status_code >= 500:
            raise ExtractionError(f"AI engine error {response.status_code}", retryable=True)
        if response.status_code >= 400:
            raise ExtractionError(f"AI engine rejected the call: {response.status_code}", retryable=False)

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise ExtractionError("AI engine response has no message content", retryable=False) from error
        # Models can answer with null content (a filtered or empty completion): an empty answer, handled as a refusal
        return content if isinstance(content, str) else ""
