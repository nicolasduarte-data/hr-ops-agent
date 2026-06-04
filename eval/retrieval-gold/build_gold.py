#!/usr/bin/env python3
"""Build the retrieval gold set for retrieval evaluation.

Design principles:
  • Vocabulary divergence: queries deliberately avoid copying exact phrases
    from the corpus — they use paraphrases, synonyms, or describe the task
    rather than quoting system names. This is the key mitigation against
    circularity in retrieval evaluation.

  • Two pipelines: process doc queries (search_process_docs) and ticket
    queries (lookup_known_issues), evaluated separately.

  • Human review: 30 pairs are marked human_reviewed=True — these are the
    gold-grade pairs where the mapping was verified by reading the source doc.
    Remaining pairs are silver (auto-generated, reasonable confidence).

  • Coverage: all 9 M2 policy docs + 5 original docs + the 3 smoke-note
    failure cases (PA30, EIB supervisory org, RITM routing) must be covered.

Usage:
    uv run python eval/retrieval-gold/build_gold.py
    → writes eval/retrieval-gold/gold_set.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path

OUTPUT = Path(__file__).parent / "gold_set.jsonl"


def q(
    qid: str,
    query: str,
    relevant_docs: list[str],
    pipeline: str,  # "process" | "ticket"
    query_type: str,  # "semantic" | "lexical" | "hybrid"
    divergence_note: str,
    human_reviewed: bool = False,
) -> dict:
    return {
        "qid": qid,
        "query": query,
        "relevant_docs": relevant_docs,
        "pipeline": pipeline,
        "query_type": query_type,
        "divergence_note": divergence_note,
        "human_reviewed": human_reviewed,
    }


GOLD: list[dict] = [

    # -----------------------------------------------------------------------
    # PROCESS DOC QUERIES — search_process_docs pipeline
    # -----------------------------------------------------------------------

    # requesting-time-off.md
    q("pq001", "how do I take vacation days at Meridian",
      ["requesting-time-off.md"], "process", "semantic",
      "query: 'vacation days' → corpus: 'PTO (Vacation)'; 'take' vs 'request'", True),
    q("pq002", "I need to be out sick next week — what do I do in the system",
      ["requesting-time-off.md"], "process", "semantic",
      "query: 'be out sick' → corpus: 'Sick Leave'; 'system' not named", True),
    q("pq003", "half day absence Workday",
      ["requesting-time-off.md"], "process", "hybrid",
      "query uses 'absence' (domain word) + 'Workday' (system name)", True),
    q("pq004", "where do I check my remaining time off balance",
      ["requesting-time-off.md"], "process", "semantic",
      "query: 'remaining time off balance' → corpus: 'Balance panel' + 'accrued balance'", True),
    q("pq005", "family medical leave policy FMLA",
      ["requesting-time-off.md"], "process", "hybrid",
      "query uses FMLA acronym + 'family medical leave' paraphrase", True),

    # updating-personal-data-ec.md
    q("pq006", "how to change my home address in the HR system",
      ["updating-personal-data-ec.md"], "process", "semantic",
      "query: 'change my home address' → corpus section on address updates in EC", True),
    q("pq007", "update emergency contact information",
      ["updating-personal-data-ec.md"], "process", "semantic",
      "query: paraphrase of 'emergency contact' section", True),
    q("pq008", "bank account details payroll deposit",
      ["updating-personal-data-ec.md"], "process", "hybrid",
      "query: 'bank account' + 'payroll deposit' → corpus: direct deposit section", True),
    q("pq009", "SuccessFactors personal information change request",
      ["updating-personal-data-ec.md"], "process", "lexical",
      "query: exact 'SuccessFactors' + 'personal information'", False),

    # benefits-open-enrollment.md
    q("pq010", "picking my health insurance plan for next year",
      ["benefits-open-enrollment.md"], "process", "semantic",
      "query: 'picking' + 'next year' → corpus: enrollment window, plan selection", True),
    q("pq011", "when is the enrollment window for benefits",
      ["benefits-open-enrollment.md"], "process", "semantic",
      "query: 'enrollment window' → corpus: open enrollment dates/window section", True),
    q("pq012", "dental and vision coverage selection",
      ["benefits-open-enrollment.md"], "process", "hybrid",
      "query: 'dental and vision' → corpus: specific plan types section", True),
    q("pq013", "how do I add a dependent to my medical plan",
      ["benefits-open-enrollment.md"], "process", "semantic",
      "query: 'add a dependent' → corpus: dependent enrollment section", False),

    # annual-performance-review.md
    q("pq014", "submitting my end of year self-assessment",
      ["annual-performance-review.md"], "process", "semantic",
      "query: 'end of year self-assessment' → corpus: self-evaluation / review cycle section", True),
    q("pq015", "manager rating calibration process",
      ["annual-performance-review.md"], "process", "semantic",
      "query: 'manager rating calibration' → corpus: rating normalization section", True),
    q("pq016", "goal setting in SuccessFactors performance module",
      ["annual-performance-review.md"], "process", "hybrid",
      "query: 'SuccessFactors' + 'goal setting' + 'performance module'", False),
    q("pq017", "360 feedback collection peer review",
      ["annual-performance-review.md"], "process", "semantic",
      "query: '360 feedback' + 'peer review' → corpus: multi-rater section", False),

    # submitting-expenses.md
    q("pq018", "get reimbursed for business travel costs",
      ["submitting-expenses.md"], "process", "semantic",
      "query: 'reimbursed' + 'business travel costs' → corpus: expense submission process", True),
    q("pq019", "attach a receipt to my expense report in Concur",
      ["submitting-expenses.md"], "process", "hybrid",
      "query: 'Concur' (exact) + 'attach receipt' (paraphrase of upload step)", True),
    q("pq020", "mileage claim for driving to client site",
      ["submitting-expenses.md"], "process", "semantic",
      "query: 'mileage claim' + 'client site' → corpus: mileage/travel section", False),

    # internal-job-application.md
    q("pq021", "how do I apply for a different role within the company",
      ["internal-job-application.md"], "process", "semantic",
      "query: 'different role within the company' → corpus: internal mobility section", True),
    q("pq022", "internal transfer notice period requirement",
      ["internal-job-application.md"], "process", "semantic",
      "query: 'notice period' → corpus: transfer timeline / requirements section", True),
    q("pq023", "can I apply for a promotion through the HR portal",
      ["internal-job-application.md"], "process", "semantic",
      "query: 'promotion' + 'HR portal' → corpus: internal application process", False),

    # accessing-pay-statements.md
    q("pq024", "how to download my payslip",
      ["accessing-pay-statements.md"], "process", "semantic",
      "query: 'download my payslip' → corpus: pay statement access section", True),
    q("pq025", "where can I find my salary breakdown for tax purposes",
      ["accessing-pay-statements.md"], "process", "semantic",
      "query: 'salary breakdown for tax' → corpus: year-end tax document section", True),
    q("pq026", "historical payment records Workday",
      ["accessing-pay-statements.md"], "process", "hybrid",
      "query: 'historical payment records' + 'Workday'", False),

    # completing-compliance-training.md
    q("pq027", "mandatory data privacy course completion deadline",
      ["completing-compliance-training.md"], "process", "semantic",
      "query: 'data privacy course' + 'deadline' → corpus: required training list + due dates", True),
    q("pq028", "how to mark a training as done in the learning management system",
      ["completing-compliance-training.md"], "process", "semantic",
      "query: 'mark as done' + 'learning management system' → corpus: LMS completion steps", True),
    q("pq029", "code of conduct training LMS",
      ["completing-compliance-training.md"], "process", "hybrid",
      "query: 'code of conduct' + 'LMS' — lexical on LMS acronym", False),

    # equipment-request-process.md
    q("pq030", "I need a new laptop — how do I request one",
      ["equipment-request-process.md"], "process", "semantic",
      "query: 'new laptop' + 'request' → corpus: equipment request process via ServiceNow", True),
    q("pq031", "ergonomic chair or standing desk approval process",
      ["equipment-request-process.md"], "process", "semantic",
      "query: 'ergonomic' + 'standing desk' → corpus: ergonomic accommodation section", True),
    q("pq032", "replace broken monitor peripheral request",
      ["equipment-request-process.md"], "process", "hybrid",
      "query: 'broken monitor' + 'peripheral' → corpus: replacement equipment section", False),

    # Original docs (hr-processes.md, onboarding-checklist.md)
    q("pq033", "steps for new employee orientation first week",
      ["onboarding-checklist.md"], "process", "semantic",
      "query: 'new employee orientation' → corpus: onboarding checklist first-week section", True),
    q("pq034", "offboarding steps when an employee leaves",
      ["hr-processes.md"], "process", "semantic",
      "query: 'offboarding' + 'employee leaves' → corpus: offboarding section in hr-processes.md", True),
    q("pq035", "job leveling framework Meridian grade structure",
      ["hr-processes.md"], "process", "hybrid",
      "query: 'job leveling' + 'grade structure' → corpus: compensation/grading section", False),

    # -----------------------------------------------------------------------
    # TICKET RECORD QUERIES — lookup_known_issues pipeline
    # Smoke-note failures must be covered (PA30, EIB, RITM)
    # -----------------------------------------------------------------------

    # PA30 — SAP R/3 HR master data transaction (SMOKE NOTE CASE)
    q("tq001", "PA30 locked by another user unable to edit employee record",
      ["inc-007-ec-position-not-syncing.md",
       "inc-008-ec-workflow-approval-stuck.md",
       "inc-009-ec-org-chart-not-updating.md"],
      "ticket", "lexical",
      "PA30 is an exact SAP T-code — dense models struggle; lexical match required. "
      "Note: PA30-specific incident may be in known-issues.md ISSUE-005; "
      "any ticket with lock/HR-master-data context is relevant", True),
    q("tq002", "SAP R/3 HR master data record cannot be edited — object locked",
      ["inc-007-ec-position-not-syncing.md"],
      "ticket", "semantic",
      "query avoids 'PA30' entirely — semantic query for the same concept", True),

    # EIB supervisory org (SMOKE NOTE CASE)
    q("tq003", "EIB load failed date format error bulk upload compensation",
      ["inc-021-wd-eib-date-format-error.md"], "ticket", "lexical",
      "EIB is exact acronym (Enterprise Interface Builder) — lexical required for disambiguation", True),
    q("tq004", "Workday bulk import failed with validation error on date column",
      ["inc-021-wd-eib-date-format-error.md"], "ticket", "semantic",
      "vocabulary-divergent: 'bulk import' instead of 'EIB', 'date column' → should find EIB date ticket", True),
    q("tq005", "supervisory org hierarchy not showing correct manager after reorganisation",
      ["inc-020-wd-org-hierarchy-error.md"], "ticket", "semantic",
      "query: 'supervisory org hierarchy' diverges from EIB context — tests that EIB org errors don't conflate", True),
    q("tq006", "EIB supervisory organisation validation error on load",
      ["inc-020-wd-org-hierarchy-error.md",
       "inc-021-wd-eib-date-format-error.md"],
      "ticket", "hybrid",
      "SMOKE NOTE: EIB supervisory org — dense conflates EIB error types; hybrid should disambiguate", True),

    # RITM routing (SMOKE NOTE CASE)
    q("tq007", "RITM routed to wrong team in ServiceNow",
      ["inc-024-sn-ritm-routing-wrong-team.md"], "ticket", "lexical",
      "RITM is exact ITSM term — lexical match critical; dense conflates RITM-not-working patterns", True),
    q("tq008", "ServiceNow request item assigned to incorrect fulfilment group",
      ["inc-024-sn-ritm-routing-wrong-team.md"], "ticket", "semantic",
      "vocabulary-divergent: 'request item' instead of 'RITM', 'fulfilment group' instead of 'routing team'", True),
    q("tq009", "approval workflow stuck in ServiceNow not progressing",
      ["inc-026-sn-approval-email-not-sent.md",
       "inc-008-ec-workflow-approval-stuck.md"],
      "ticket", "semantic",
      "query: 'approval workflow stuck' → should find SN approval email ticket, not RITM routing", False),

    # SuccessFactors EC issues
    q("tq010", "employee position title not updating after promotion in EC",
      ["inc-007-ec-position-not-syncing.md"], "ticket", "semantic",
      "query: 'position title not updating after promotion' → corpus: EC position sync failure", True),
    q("tq011", "org chart shows old manager after reporting line change",
      ["inc-009-ec-org-chart-not-updating.md"], "ticket", "semantic",
      "query: 'org chart shows old manager' → corpus: EC org chart update failure", True),
    q("tq012", "role-based permissions access denied in Employee Central",
      ["inc-010-ec-rbp-access-denied.md"], "ticket", "hybrid",
      "query: 'role-based permissions' + 'Employee Central' — RBP acronym lexical", True),
    q("tq013", "EC approval workflow is stuck employee cannot complete onboarding task",
      ["inc-008-ec-workflow-approval-stuck.md"], "ticket", "semantic",
      "query: 'approval workflow stuck' + 'onboarding task' → corpus: EC workflow approval issue", False),

    # ECP payroll issues
    q("tq014", "payslip not generated for employee after payroll run",
      ["inc-011-ecp-payslip-not-generated.md"], "ticket", "semantic",
      "query: 'payslip not generated' → corpus: ECP payslip generation failure", True),
    q("tq015", "incorrect tax code applied to employee in payroll",
      ["inc-012-ecp-tax-code-incorrect.md"], "ticket", "semantic",
      "query: 'incorrect tax code' → corpus: ECP tax code correction ticket", True),
    q("tq016", "bank account for salary payment not updated in the system",
      ["inc-013-ecp-bank-details-not-updating.md"], "ticket", "semantic",
      "query: 'bank account for salary payment not updated' → corpus: ECP bank detail ticket", False),

    # Workday issues
    q("tq017", "absence accrual balance showing wrong number in Workday",
      ["inc-017-wd-absence-balance-incorrect.md"], "ticket", "semantic",
      "query: 'absence accrual balance wrong' → corpus: WD absence balance ticket", True),
    q("tq018", "new manager not showing up after org change in Workday",
      ["inc-018-wd-manager-change-not-reflected.md"], "ticket", "semantic",
      "query: 'new manager not showing up' → corpus: WD manager change replication", False),
    q("tq019", "benefits enrollment window missing from Workday home screen",
      ["inc-019-wd-benefits-window-missing.md"], "ticket", "semantic",
      "query: 'benefits enrollment window missing' → corpus: WD benefits window ticket", False),
    q("tq020", "CPI integration sync delay SuccessFactors to Workday headcount mismatch",
      ["inc-023-wd-to-sf-headcount-mismatch.md",
       "inc-022-wd-coreconnect-sync-delay.md"],
      "ticket", "hybrid",
      "query: 'CPI integration' (lexical) + 'headcount mismatch' (semantic)", True),

    # Okta issues
    q("tq021", "MFA setup loop keeps asking me to enrol again",
      ["inc-031-okta-mfa-enrollment-loop.md"], "ticket", "semantic",
      "query: 'MFA setup loop' → corpus: Okta MFA enrollment loop ticket", True),
    q("tq022", "application not appearing in Okta dashboard after being assigned",
      ["inc-032-okta-app-assignment-missing.md"], "ticket", "semantic",
      "query: 'application not appearing' → corpus: Okta app assignment ticket", False),
    q("tq023", "Azure AD sync delay Okta user not deactivated after offboarding",
      ["inc-034-okta-azure-ad-sync-delay.md"], "ticket", "hybrid",
      "query: 'Azure AD sync' (lexical) + 'deactivated after offboarding' (semantic)", False),

    # Onboarding issues
    q("tq024", "new hire portal tasks not visible on first day",
      ["inc-014-onb-portal-tasks-not-visible.md"], "ticket", "semantic",
      "query: 'portal tasks not visible' → corpus: ONB portal tasks ticket", True),
    q("tq025", "compliance document e-signature keeps looping back to start",
      ["inc-016-onb-compliance-doc-signature-loop.md"], "ticket", "semantic",
      "query: 'e-signature keeps looping' → corpus: ONB compliance doc signature loop", False),

]


def main() -> None:
    total = len(GOLD)
    human_reviewed = sum(1 for g in GOLD if g["human_reviewed"])
    process = sum(1 for g in GOLD if g["pipeline"] == "process")
    ticket = sum(1 for g in GOLD if g["pipeline"] == "ticket")
    semantic = sum(1 for g in GOLD if g["query_type"] == "semantic")
    lexical = sum(1 for g in GOLD if g["query_type"] == "lexical")
    hybrid = sum(1 for g in GOLD if g["query_type"] == "hybrid")

    with OUTPUT.open("w", encoding="utf-8") as f:
        for entry in GOLD:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Gold set written to {OUTPUT}")
    print(f"  Total pairs:    {total}")
    print(f"  Human-reviewed: {human_reviewed}")
    print(f"  Process queries: {process}")
    print(f"  Ticket queries:  {ticket}")
    print(f"  Semantic:        {semantic}")
    print(f"  Lexical:         {lexical}")
    print(f"  Hybrid:          {hybrid}")


if __name__ == "__main__":
    main()
