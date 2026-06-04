# INC-0071144 — Headcount Mismatch Between Workday and SF EC Reports

**system_affected**: Workday_Integration
**resolution_status**: in-progress
**reported_date**: 2026-01-08
**resolved_date**:
**ticket_type**: incident
**reported_by**: People Analytics (via HR Ops)

## Description

The monthly headcount reconciliation report (run by People Analytics on the 5th of each month) shows a 3-employee discrepancy between Workday subsidiary headcount (247) and SF EC headcount for the same subsidiary population (244). The discrepancy has persisted for 2 months. All three unmatched employees exist in Workday but do not have a corresponding active EC record.

## Root Cause (Preliminary)

Three employees were hired directly into the Workday subsidiary tenant in November via a one-off manual hire process (bypassing the standard onboarding workflow). The standard onboarding workflow triggers the Workday→EC sync via the CPI integration. Since these employees were hired manually in Workday without triggering the workflow, the CPI integration never received a "new hire" event for them, and EC records were never created.

The employees have been working at Meridian for 2 months without EC records — they are not enrolled in SF ECP payroll (subsidiary still runs on Workday Payroll, so no payroll impact yet) but they are missing from benefits eligibility, performance review, and LMS compliance training assignment.

## Workaround

People Analytics confirmed the 3 affected Workday IDs (WD-5311, WD-5312, WD-5318). HRIS is creating manual EC records for all three. Compliance training will be assigned retroactively once EC records are active.

## Resolution

In progress. EC record creation for 3 employees underway (ETA 2026-01-10). HRIS is also conducting a broader audit of the Workday subsidiary for any other manual hires that may have bypassed the standard workflow over the past 12 months.

Long-term: Meridian will mandate that all subsidiary hires go through the standard onboarding workflow. Manual hire process in Workday is being disabled.

## Related

- CPI iFlow: `Workday-to-EC-NewHire-Sync` — triggered by Workday hire business process completion event
- People Analytics monthly reconciliation: `reports/headcount-reconciliation-monthly.xlsx`
