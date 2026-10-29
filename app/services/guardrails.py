"""
Turns whatever the AI engine answered into a structured extraction, or says clearly why it cannot.

Pure functions, no I/O. They undo the kinds of noise LLMs produce (and the mock reproduces): Markdown fences, prose
around the JSON, renamed or extra keys, single quotes, unquoted keys, output cut short. They never fill a missing
field: that is the fallback's decision, and the message is never made up.
"""

import ast
import json
import re
from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class Extraction:
    to: str | None
    message: str | None
    type: str | None


class RefusalKind(StrEnum):
    # The model declined (policy, safety): asking again may get an answer
    POLICY = "policy"
    # The model says the request lacks a recipient or channel: asking again gets the same answer
    MISSING_INFORMATION = "missing_information"


class AIRefusal(Exception):
    """The answer contains no JSON object at all."""

    def __init__(self, kind: RefusalKind, text: str) -> None:
        super().__init__(f"AI refused ({kind}): {text[:200]}")
        self.kind = kind


class MalformedOutput(Exception):
    """There is a JSON-like object, but not even the repairs can read it (typically cut inside a value)."""


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_MISSING_INFORMATION = re.compile(
    r"unable to identify|could not (?:find|identify)|missing|no (?:he podido|puedo|se puede) identificar|falta",
    re.IGNORECASE,
)
_UNQUOTED_KEY = re.compile(r"([{,]\s*)([A-Za-z_][\w-]*)\s*:")
_TRAILING_NOISE = re.compile(r"(?:\s|\.\.\.|…|,)+$")

_KEY_SYNONYMS = {
    "to": "to",
    "recipient": "to",
    "destination": "to",
    "destinatario": "to",
    "message": "message",
    "body": "message",
    "text": "message",
    "content": "message",
    "mensaje": "message",
    "type": "type",
    "channel": "type",
    "method": "type",
    "tipo": "type",
    "canal": "type",
}
_TYPE_SYNONYMS = {
    "email": "email",
    "e-mail": "email",
    "mail": "email",
    "correo": "email",
    "sms": "sms",
    "text": "sms",
    "phone": "sms",
    "teléfono": "sms",
    "telefono": "sms",
}


def parse_ai_output(text: str) -> Extraction:
    candidate = _find_object(_strip_fences(text))
    if candidate is None:
        kind = RefusalKind.MISSING_INFORMATION if _MISSING_INFORMATION.search(text) else RefusalKind.POLICY
        raise AIRefusal(kind, text)
    return _normalise(_load(candidate))


def _strip_fences(text: str) -> str:
    fenced = _FENCE.search(text)
    return fenced.group(1) if fenced else text


def _find_object(text: str) -> str | None:
    """The first balanced {...}, skipping braces inside strings; the rest of the text if it never closes."""
    start = text.find("{")
    if start == -1:
        return None
    depth, quote, escaped = 0, None, False
    for index in range(start, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text[start:]


def _load(candidate: str) -> dict:
    for attempt in (candidate, _close_truncated(candidate)):
        if attempt is None:
            continue
        for parse in (json.loads, ast.literal_eval, _parse_with_quoted_keys):
            try:
                data = parse(attempt)
            except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
                continue
            if isinstance(data, dict):
                return data
    raise MalformedOutput(f"Unreadable AI output: {candidate[:200]}")


def _parse_with_quoted_keys(candidate: str) -> object:
    return json.loads(_UNQUOTED_KEY.sub(r'\1"\2":', candidate))


def _close_truncated(candidate: str) -> str | None:
    """
    Closes an object that was cut after its last complete value ('... "type": "email" ...'). An object cut inside a
    string stays unreadable after closing it, so half a message is never delivered.
    """
    trimmed = _TRAILING_NOISE.sub("", candidate)
    missing = trimmed.count("{") - trimmed.count("}")
    if missing <= 0:
        return None
    return trimmed + "}" * missing


def _normalise(data: dict) -> Extraction:
    fields: dict[str, str | None] = {}
    for key, value in data.items():
        canonical = _KEY_SYNONYMS.get(str(key).strip().lower())
        # Unknown keys (confidence, latency_ms...) are dropped; the first synonym found wins
        if canonical and canonical not in fields:
            fields[canonical] = _as_text(value)
    raw_type = fields.get("type")
    return Extraction(
        to=fields.get("to"),
        message=fields.get("message"),
        type=_TYPE_SYNONYMS.get(raw_type.lower()) if raw_type else None,
    )


def _as_text(value: object) -> str | None:
    if value is None or isinstance(value, bool | dict | list):
        return None
    text = str(value).strip()
    return text or None
