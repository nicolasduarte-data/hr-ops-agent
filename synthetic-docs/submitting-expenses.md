# Submitting Expense Reports — Meridian HR Guide

**System**: SAP Concur Expense
**Applies to**: All employees with T&E (travel and expense) reimbursement needs
**Last updated**: 2026-01-18
**Owner**: Finance / Accounts Payable

---

## Overview

All business expense reimbursements at Meridian are processed through SAP Concur. Expense reports must be submitted within **30 days of the expense date**. Late submissions (>60 days) require manager and Finance approval to process and may be declined.

Concur is accessible at `concur.meridian-hr.internal` or via the **SAP Concur mobile app** (iOS and Android).

---

## Creating an Expense Report

1. Log into Concur at `concur.meridian-hr.internal`.
2. Click **Expense** → **Create New Report**.
3. Enter:
   - **Report Name** — use the format: `[Month Year] — [Trip or project name]` (e.g., "March 2026 — Chicago Client Visit")
   - **Report Date** — last date of the expense period
   - **Business Purpose** — required; be specific (e.g., "Client meeting with Acme Corp to discuss Q2 renewal")
   - **Cost Center** — pre-populated from your EC profile; change only if the expense should charge to a different cost center (requires manager approval)
4. Click **Next** to open the expense entry screen.

---

## Adding Expense Lines

For each expense:

1. Click **New Expense**.
2. Select **Expense Type** from the dropdown:
   - `Airfare` · `Hotel` · `Meals (Business)` · `Ground Transportation` · `Conference Registration` · `Other Business Expense`
3. Enter: Date, Vendor, Amount, Currency, Business Purpose (per-line).
4. Attach a receipt:
   - **Mobile**: use the Concur app to photo-capture receipts. Receipt OCR auto-fills fields — review for accuracy before saving (OCR is unreliable for handwritten receipts and low-contrast images; see ISSUE-003 in known-issues.md).
   - **Desktop**: drag-and-drop receipt images into the **Receipts** tab, then link them to expense lines.
5. Receipts are required for all expenses ≥$25. Expenses without receipts trigger a **Missing Receipt** policy alert — Finance may reject the line.

---

## Meal Per Diem vs. Actuals

Meridian uses **actual receipts** for meals, not per diem, except for international travel where per diem rates apply. For international travel, confirm the applicable per diem with Finance before the trip.

**Meal limits (domestic)**:
- Breakfast: $25
- Lunch: $40
- Dinner: $75
- Team meals (≥3 people): $80/person with attendee list required in Concur comments

Amounts over the limit trigger a **Policy Exception** alert. You may still submit with a justification note; Finance reviews and may approve or reject.

---

## Submitting and Approval Workflow

1. Review the **Audit Trail** panel on the right — Concur flags policy violations in real time. Resolve or add justification notes before submitting.
2. Click **Submit Report**. Your manager receives an approval request via email and Concur inbox.
3. **Approval SLA**: managers should approve within 5 business days. Finance processes approved reports in the next weekly AP run (Thursdays).
4. Reimbursement: deposited to the bank account on file in SF EC within 3–5 business days of Finance processing.

---

## Corporate Card Expenses

If you have a Meridian corporate card, card transactions auto-import into your Concur wallet within 2 business days of the charge. You still need to:
1. Assign each imported transaction to an expense report.
2. Attach receipts for transactions ≥$25.
3. Submit the report within 30 days.

**Unassigned card charges older than 30 days** generate a Concur policy alert and are escalated to Finance for review.

---

## Common Issues

| Problem | Fix |
|---|---|
| Receipt OCR filled wrong amount | Edit the field manually before saving — OCR is a prefill only |
| "Policy Violation" flag on a valid expense | Add a justification note in the comment field; manager approves the exception |
| Can't find my corporate card transactions | Card transactions take 2 business days to appear; also confirm card is linked in **Profile → Connected Services** |
| Report rejected by Finance | Check the rejection reason in the report's **Audit Trail**; correct and resubmit |
| Expense older than 60 days — system blocks submission | Contact Finance (`ap@meridian-hr.internal`) for a manual override approval |

---

## Contact

- **Expense policy questions**: Finance Helpdesk (`finance-help@meridian-hr.internal`)
- **Concur technical issues**: `hris-support@meridian-hr.internal`
- **Urgent reimbursement**: AP team (`ap@meridian-hr.internal`)
