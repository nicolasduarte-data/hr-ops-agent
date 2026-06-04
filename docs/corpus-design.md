# hr-ops-agent — Synthetic Corpus Design

Design spec for the synthetic document corpus, grounded in **real enterprise HRIS/IT systems**
and authored under a **clean-room rule**. Built in two phases — a minimal corpus and a
scale-up. The retrieval evaluation is only as credible as
this corpus.

---

## Why real systems (not generic invented content)

1. **Authenticity** — content grounded in real Workday / SuccessFactors / ServiceNow
   terminology reads like internal documentation written by someone who has worked in
   enterprise HR IT. Generic invented content reads tutorial-grade, and a domain reader spots
   the difference immediately.
2. **It makes the hybrid-retrieval result testable** — real systems carry exact-match
   vocabulary (T-codes, module acronyms, integration terms) that dense-only retrieval misses.
   That is exactly the gap that hybrid BM25+dense+RRF closes. **This corpus is the demo
   case for hybrid retrieval.**

---

## ⚠️ Clean-Room Principle (non-negotiable)

**The systems are real. The company, the people, the data, and the configuration are invented.**

| ✅ Use (public knowledge) | ❌ Never use (proprietary) |
|---|---|
| Public vendor terminology, module names, standard documented workflows | employer-specific custom field names, custom business-process definitions, internal naming |
| Standard error patterns / known issues from public community forums + vendor notes | a real internal known-issue register, ticket numbers, or RCA notes |
| Standard escalation patterns (e.g. SF P1 → SAP support via Launchpad) | real internal escalation contacts, SLAs, or support tenant IDs |
| Fictional company, employees, org structure | Any real employee data, real org charts, real configs |

**The test — apply to every sentence:** *"Could I have written this from public Workday / SAP /
SuccessFactors documentation, certification material, or community forums — or only from
working inside a specific employer's tenant?"* If only the latter → genericize until public-knowledge-
equivalent, or cut. The author works with these systems at a large enterprise daily; the line between
"how SAP works" and "how a specific employer's SAP works" is easy to cross unnoticed. This rule is the guard.

---

## The fictional company

A mid-size enterprise (~3,000 employees), working name **"Meridian"** (change freely). The
stack is chosen so every named system coexists for a *realistic reason* and the docs interlock:

| Layer | System | Role in the fiction |
|---|---|---|
| Core HCM (system of record) | **SAP SuccessFactors** — Employee Central (EC) | HR master data, self-service |
| HR modules | SF Onboarding (ONB), Performance & Goals (PMGM), Recruiting (RCM), Learning (LMS) | Process coverage |
| Payroll | SF Employee Central Payroll (ECP) | Pay statements, replication issues |
| Second HCM | **Workday** | Acquired subsidiary runs Workday; mid-integration — justifies both systems + rich integration known-issues |
| ITSM | **ServiceNow** (HR Service Delivery + IT) | Where tickets/issues route |
| Expense | **SAP Concur** | Expense workflow |
| Identity | **Okta / Azure AD** (SSO) | Provisioning + login known-issues |

The "SAP shop mid-migration to Workday, plus a Workday subsidiary" framing is realistic, gives
every named system a reason to exist, and generates authentic cross-system known-issues — the
kind an HR IT auditor actually sees.

---

## Document inventory

> **Count note:** the tables below list document *categories*. To reach the ≥40-doc / ~150-chunk
> target (Corpus M2), each category scales to multiple instances — **~10–12 policy docs**
> (2–3 per process area) **+ ~28–32 individual IT-ticket records** (a realistic KB has dozens).
> The ticket records carry the volume.

### `search_process_docs` — unstructured policy/process (semantic-primary)
| Document | System |
|---|---|
| Requesting Time Off | Workday |
| Updating Personal Data in Employee Central | SF EC |
| New-Hire Onboarding (Onboarding 2.0) | SF ONB |
| Benefits Open Enrollment | Workday |
| Submitting Expenses | SAP Concur |
| Annual Performance Review | SF PMGM |
| Internal Job Application | SF RCM |
| Completing Compliance Training | SF LMS |
| Accessing Pay Statements | SF ECP |

### `lookup_known_issues` — structured issue records (BM25-heavy, atomic)
| Issue | System(s) |
|---|---|
| SSO login loop after password reset | Workday / Okta |
| EC effective-dated change not replicating to payroll | SF EC → ECP |
| Concur receipt OCR fails on mobile upload | Concur |
| Provisioning ticket not auto-created | Workday → ServiceNow |
| New-hire account not provisioned | SF ONB → Azure AD |
| Transaction PA30 locked by another user | SAP HCM |
| EIB load failed — supervisory org validation | Workday |

### `get_it_scope` — ownership boundaries
HRIS team (SF config / RBP) · IAM (SSO / provisioning) · Integration team (CPI / Boomi / EIB) ·
Payroll Ops (ECP) · ServiceNow admin (ITSM).

### `get_escalation_path` — routing rules
SF P1 → SAP support (Launchpad) · Workday issue → Workday Community / named support · integration
failure → Integration on-call · access issue → IAM queue.

---

## Exact-match vocabulary targets (the hybrid-retrieval gold)

Terms dense-only retrieval misses and BM25 catches — seed deliberately so hybrid retrieval has demonstrable wins:

- **SAP T-codes:** `PA30`, `PA40`, `PA20`, `SE16`, `PA61`
- **SuccessFactors modules:** `EC`, `ECP`, `ONB`, `PMGM`, `RCM`, `LMS`, `RBP`
- **Workday:** `EIB`, Workday Studio, supervisory organization, business process (`BP`), tenant
- **Integration:** SAP `CPI`, Boomi, middleware, `BIB`
- **HR:** `PTO`, `FMLA`, `LOA`, `FTE`
- **ITSM:** ServiceNow, `INC` (incident), `RITM` (request), `SLA`

> **Demo case for hybrid retrieval:** query *"PA30 locked"* — dense embedding has no concept of PA30; BM25
> nails the exact token. That one example proves why hybrid beats dense-only. Capture it in the eval.

---

## Metadata

`system_affected` is a **controlled vocabulary** drawn from the system table above. It drives
the metadata pre-filters (`lookup_known_issues` filters on `system_affected` +
`resolution_status`). Keep the value set fixed and documented.

---

Every corpus document passes the clean-room provenance gate (see `provenance.md`).
