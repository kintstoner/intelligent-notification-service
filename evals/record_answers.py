"""
Sends every evaluation case to the AI endpoint at PROVIDER_BASE_URL, with the service's own system prompt and
client, and saves the raw answers. In production this points at the real model's gateway; against the challenge's
mock it shows what the mock answers.

    python evals/record_answers.py evals/answers/<model>.jsonl
"""

import asyncio
import json
import sys

import httpx
from judge import CASES

from config import settings
from services.extractor import Extractor


async def ask_all() -> list[str]:
    headers = {"X-API-Key": settings.provider_api_key}
    async with httpx.AsyncClient(base_url=settings.provider_base_url, headers=headers) as client:
        extractor = Extractor(client, timeout_s=settings.ai_timeout_s)
        return await asyncio.gather(*(extractor.extract(case["user_input"]) for case in CASES.values()))


def record(path: str) -> None:
    answers = asyncio.run(ask_all())
    lines = [
        json.dumps({"id": case_id, "answer": answer}, ensure_ascii=False)
        for case_id, answer in zip(CASES, answers, strict=True)
    ]
    with open(path, "w", encoding="utf-8") as output:
        output.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    record(sys.argv[1])
