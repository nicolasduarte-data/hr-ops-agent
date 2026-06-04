"""Smoke eval — wiring check.

~20 hand-written queries with expected tool(s). Runs against the live agent.
Not a metrics framework — just prints hits/misses to confirm routing works end-to-end.
The real eval harness (precision@k, tool accuracy, confusion matrix) lives in run_eval.py.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.orchestrator import run_agent  # noqa: E402

SMOKE_CASES = [
    # (query, expected_tools_subset)
    ("How do I request time off in Workday?", {"search_process_docs"}),
    ("What are the steps for PTO request?", {"search_process_docs"}),
    ("How does new hire onboarding work?", {"search_process_docs"}),
    ("How do I submit an expense report in Concur?", {"search_process_docs"}),
    ("How do I enroll in benefits during open enrollment?", {"search_process_docs"}),
    ("My Workday is stuck in an SSO login loop after resetting my password.", {"lookup_known_issues"}),
    ("PA30 is locked by another user, what do I do?", {"lookup_known_issues"}),
    ("My expense receipt OCR failed in Concur mobile.", {"lookup_known_issues"}),
    ("The new hire provisioning ticket was never created in ServiceNow.", {"lookup_known_issues"}),
    ("EIB load is failing with supervisory org validation error.", {"lookup_known_issues"}),
    ("Who manages Okta and Azure AD at Meridian?", {"get_it_scope"}),
    ("Which team owns the CPI iFlow integrations?", {"get_it_scope"}),
    ("Who handles SuccessFactors RBP configuration?", {"get_it_scope"}),
    ("Who is responsible for Workday EIB templates?", {"get_it_scope"}),
    ("How do I escalate a P1 issue to the IAM team?", {"get_escalation_path"}),
    ("What is the SLA for a P2 Integration team ticket?", {"get_escalation_path"}),
    # Multi-tool queries (expect both)
    (
        "My Workday access isn't working and I don't know who to call.",
        {"lookup_known_issues", "get_escalation_path"},
    ),
    (
        "The new hire has no Azure AD account on Day 1. This is a P1. Who do I contact and how?",
        {"lookup_known_issues", "get_it_scope", "get_escalation_path"},
    ),
    (
        "EC to ECP replication failed on payroll run day. Who owns this and what is the P1 SLA?",
        {"lookup_known_issues", "get_escalation_path"},
    ),
    (
        "How do I request time off, and who do I contact if Workday is unavailable?",
        {"search_process_docs", "get_escalation_path"},
    ),
]


@dataclass
class EvalResult:
    query: str
    expected: set[str]
    actual: set[str]
    hit: bool


def run_smoke_eval() -> None:
    results: list[EvalResult] = []

    for query, expected in SMOKE_CASES:
        print(f"  Query: {query[:80]}...")
        try:
            out = run_agent(query)
            actual = set(out["tools_called"])
            # Hit = expected tools are a subset of actual (partial credit for multi-tool)
            hit = expected.issubset(actual)
        except Exception as exc:
            print(f"    ERROR: {exc}")
            actual = set()
            hit = False

        results.append(EvalResult(query=query, expected=expected, actual=actual, hit=hit))
        status = "✓" if hit else "✗"
        print(f"    {status} expected={expected} actual={actual}")

    hits = sum(1 for r in results if r.hit)
    total = len(results)
    pct = (100 * hits // total) if total > 0 else 0
    print(f"\nSmoke eval: {hits}/{total} ({pct}%)")

    if hits < total * 0.8:
        print("WARNING: Below 80% hit rate — check tool descriptions and system prompt.")


if __name__ == "__main__":
    run_smoke_eval()
