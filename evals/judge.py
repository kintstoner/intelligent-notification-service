"""Judges AI answers to the evaluation cases with the same rules the service applies."""

import json
import sys
from pathlib import Path

EVALS = Path(__file__).parent
ANSWERS = EVALS / "answers"
sys.path.insert(0, str(EVALS.parent / "app"))

from services.processor import AnswerRejected, interpret_answer  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


CASES = {case["id"]: case for case in load_jsonl(EVALS / "extract_cases.jsonl")}


def judge(case: dict, answer: str) -> list[str]:
    """Problems with one answer; empty when it is right."""
    expected = case["expected"]
    try:
        notification = interpret_answer(answer, case["user_input"])
    except AnswerRejected as rejection:
        if expected.get("outcome") == "no_notification":
            return []
        return [f"rejected ({rejection.reason}), expected a notification"]
    if expected.get("outcome") == "no_notification":
        return [f"sent {notification.type} to {notification.to}, expected no notification"]

    problems = [
        f"{field} is {getattr(notification, field)!r}, expected {expected[field]!r}"
        for field in ("to", "type")
        if getattr(notification, field) != expected[field]
    ]
    message = notification.message.lower()
    problems += [f"message lacks {text!r}" for text in case["message_must_contain"] if text.lower() not in message]
    problems += [f"message keeps {text!r}" for text in case["message_must_not_contain"] if text.lower() in message]
    return problems
