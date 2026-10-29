"""
Scores a file of recorded answers and prints one line per case.

    python evals/report.py evals/answers/<model>.jsonl
"""

import sys
from pathlib import Path

from judge import CASES, judge, load_jsonl


def main(path: str) -> None:
    answers = load_jsonl(Path(path))
    passed = 0
    for answer in answers:
        problems = judge(CASES[answer["id"]], answer["answer"])
        passed += not problems
        print(f"{'PASS' if not problems else 'FAIL'}  {answer['id']:<32} {'; '.join(problems)}")
    print(f"\n{passed}/{len(answers)} cases right")


if __name__ == "__main__":
    main(sys.argv[1])
