"""
Offline evaluation of the system prompt: answers a real model gave to evals/extract_cases.jsonl, judged with the same
rules the service applies (interpret_answer). See docs/prompt-eval.md for how the answers were produced.
"""

import pytest
from judge import ANSWERS, CASES, judge, load_jsonl

RUNS = sorted(ANSWERS.glob("*.jsonl"))


def test_every_run_answers_every_case():
    for run in RUNS:
        assert {answer["id"] for answer in load_jsonl(run)} == set(CASES), run.name


@pytest.mark.parametrize("run", RUNS, ids=lambda path: path.stem)
def test_the_prompt_gets_every_case_right(run):
    failures = {
        answer["id"]: problems
        for answer in load_jsonl(run)
        if (problems := judge(CASES[answer["id"]], answer["answer"]))
    }

    assert failures == {}


def test_the_judge_catches_a_wrong_answer():
    case = CASES["k6-email"]

    assert judge(case, '{"to": "otro@example.com", "message": "Enviar email diciendo hola", "type": "email"}') == [
        "to is 'otro@example.com', expected 'juan@example.com'",
        "message lacks 'paquete'",
        "message lacks 'camino'",
        "message keeps 'diciendo'",
        "message keeps 'enviar'",
    ]


def test_the_judge_catches_an_invented_notification():
    case = CASES["no-content"]

    assert judge(case, '{"to": "ana@test.com", "message": "Hola Ana", "type": "email"}') == [
        "sent email to ana@test.com, expected no notification"
    ]
