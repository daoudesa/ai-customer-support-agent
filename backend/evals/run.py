"""Score the agent's answers against a fixed set of cases.

Every case states what a correct answer must contain (`expect`) and what it
must never contain (`reject`). Rejects are the important half: they catch
invented order details and cross-customer leakage, which a win-rate on
"did it sound helpful" would miss entirely.

Usage:
    python -m evals.run                # run every case
    python -m evals.run --only refund  # only cases whose id contains "refund"
    python -m evals.run --json out.json

Each run calls the live model, so it costs a small amount per execution.
"""
import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402  (import after path fix)
from database import SessionLocal  # noqa: E402
from models import Customer  # noqa: E402

CASES = Path(__file__).parent / "cases.yaml"


@dataclass
class Result:
    case_id: str
    passed: bool
    answer: str
    missing: list = field(default_factory=list)
    leaked: list = field(default_factory=list)
    error: str = ""
    seconds: float = 0.0


def _clear_history(email: str) -> None:
    """Each case starts from a clean conversation so cases cannot affect
    each other -- except the leak case, which relies on isolation between
    customers, not within one."""
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.email == email).first()
        if customer:
            customer.messages.clear()
            db.commit()
    finally:
        db.close()


def run_case(client: TestClient, case: dict) -> Result:
    started = time.time()
    _clear_history(case["email"])

    try:
        resp = client.post(
            "/chat",
            json={"email": case["email"], "question": case["question"]},
        )
    except Exception as exc:  # network, auth, anything
        return Result(case["id"], False, "", error=str(exc),
                      seconds=time.time() - started)

    elapsed = time.time() - started

    if resp.status_code != 200:
        detail = resp.json().get("detail", resp.text)
        return Result(case["id"], False, "", error=f"HTTP {resp.status_code}: {detail}",
                      seconds=elapsed)

    answer = resp.json()["answer"]
    low = answer.lower()

    expect = [str(e).lower() for e in case.get("expect", [])]
    reject = [str(r).lower() for r in case.get("reject", [])]
    mode = case.get("match", "all")

    if mode == "any":
        missing = [] if any(e in low for e in expect) else expect
    else:
        missing = [e for e in expect if e not in low]

    leaked = [r for r in reject if r in low]

    return Result(
        case_id=case["id"],
        passed=not missing and not leaked,
        answer=answer,
        missing=missing,
        leaked=leaked,
        seconds=elapsed,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="substring filter on case id")
    ap.add_argument("--json", help="write full results to this file")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="print every answer, not just failures")
    args = ap.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set — copy .env.example to backend/.env first.")
        return 2

    cases = yaml.safe_load(CASES.read_text())
    if args.only:
        cases = [c for c in cases if args.only in c["id"]]
    if not cases:
        print("No cases matched.")
        return 2

    client = TestClient(app)
    results = []

    print(f"Running {len(cases)} cases against the live model…\n")
    for case in cases:
        r = run_case(client, case)
        results.append(r)
        mark = "PASS" if r.passed else "FAIL"
        print(f"  [{mark}] {r.case_id}  ({r.seconds:.1f}s)")
        if not r.passed or args.verbose:
            if r.error:
                print(f"         error: {r.error}")
            if r.missing:
                print(f"         missing: {', '.join(r.missing)}")
            if r.leaked:
                print(f"         LEAKED: {', '.join(r.leaked)}")
            if r.answer:
                snippet = r.answer.replace("\n", " ")[:200]
                print(f"         answer: {snippet}")

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    leaks = sum(1 for r in results if r.leaked)

    print(f"\n  {passed}/{total} passed ({passed / total * 100:.0f}%)")
    if leaks:
        print(f"  {leaks} case(s) leaked rejected content — grounding failure.")

    if args.json:
        Path(args.json).write_text(json.dumps(
            [r.__dict__ for r in results], indent=2, default=str))
        print(f"  wrote {args.json}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
