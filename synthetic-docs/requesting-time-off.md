# Requesting Time Off — Meridian HR Self-Service Guide

**System**: Workday HCM
**Applies to**: All regular employees (FTE and fixed-term)
**Last updated**: 2026-01-15
**Owner**: HR Operations

---

## Overview

All time-off requests at Meridian are submitted through Workday. This includes Paid Time Off (PTO), Sick Leave, Leaves of Absence (LOA), and FMLA-qualifying absences. Requests routed through Workday automatically notify your manager and update your absence balance in real time.

**Do not email your manager directly to request leave.** All approvals must be recorded in Workday to ensure payroll accuracy and compliance reporting.

---

## PTO and Sick Leave — Standard Requests

1. Log into Workday at `workday.meridian-hr.internal`.
2. From the **Home** screen, click **Time Off** (under the *My Team* or *My Information* worklet).
3. Select **Request** → choose the leave type from the dropdown:
   - **PTO (Vacation)** — for planned vacation, personal days
   - **Sick Leave** — for illness, medical appointments
   - **Floating Holiday** — for eligible employees; check your entitlement balance first
4. Click the calendar to select the date range. Half-day requests: check the **Half Day** toggle and select AM or PM.
5. Review your current balance in the **Balance** panel (right-hand side). Workday reflects your accrued balance as of the current pay period. Note: accruals post on the first day of each pay period — mid-period requests may show a slightly lower balance than you expect.
6. Add a note in the **Comment** field if your manager requires advance notice context.
7. Click **Submit**. Your manager receives an approval request via Workday inbox.

**Approval SLA**: Managers are expected to respond within 2 business days. If no response after 3 business days, contact your HR Business Partner.

---

## Leaves of Absence (LOA)

LOAs lasting more than 3 consecutive days require HR involvement. Do not submit a standard PTO request for an LOA.

1. Contact HR Operations at `hr-ops@meridian-hr.internal` or submit a case via ServiceNow HR Service Delivery portal (`servicenow.meridian-hr.internal`).
2. HR will initiate the **LOA business process** in Workday on your behalf.
3. You will receive a Workday task to complete the LOA request form — fill in expected start/return dates, leave reason (general category only — medical details are not required), and whether FMLA designation applies.
4. HR routes the request to Payroll Ops for coordination with SF ECP if there is a payroll impact.

---

## FMLA-Qualifying Leave

FMLA leave is administered by HR Operations. Employees may be eligible if they:
- Have worked at Meridian for at least 12 months
- Have worked ≥1,250 hours in the past 12-month period
- Work at a location with 50+ employees within 75 miles

To request FMLA designation, submit a ServiceNow HR Service Delivery case and select **Leave Administration — FMLA Request**. HR will provide the required designation forms (WH-380 series or equivalent). Medical certification is required within 15 calendar days of the request.

---

## Checking Your Absence Balances

In Workday: **Home → Time Off → Balance** (or use the global search: type "time off balance").

Balances shown:
- **PTO Available** — current accrued balance minus approved future requests
- **Sick Leave Available** — same logic
- **Carryover Cap** — PTO carries over up to 40 hours at calendar year-end; excess is forfeited on January 1

---

## Common Issues

| Problem | Fix |
|---|---|
| Balance shows 0 but you just accrued | Accruals post on the 1st of each pay period — wait 24 hours after the posting date |
| Request stuck in "Awaiting Action" for >3 days | Escalate to HR Ops — your manager's Workday inbox may be set up incorrectly |
| Can't find the Time Off worklet | Use Workday global search: type "Time Off Request" |
| LOA not showing in your record after HR initiates it | Allow 1 business day for the business process to route — check Workday inbox for pending tasks |

See also: `known-issues.md` (ISSUE-003 — Workday absence balance not syncing after manager change).

---

## Contact

- **HR Operations**: `hr-ops@meridian-hr.internal` | ServiceNow HRSD
- **Payroll questions related to leave**: `payroll-ops@meridian-hr.internal`
