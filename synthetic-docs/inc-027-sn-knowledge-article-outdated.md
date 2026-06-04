# INC-0071401 — ServiceNow Knowledge Article Contains Outdated ECP Payroll Process

**system_affected**: ServiceNow_HRSD
**resolution_status**: resolved
**reported_date**: 2025-12-18
**resolved_date**: 2025-12-20
**ticket_type**: incident
**reported_by**: Payroll Operations

## Description

Multiple employees (4 reports in December) followed instructions in ServiceNow Knowledge Base article KB-00441 ("How to View Your Pay Statement") and submitted ITSM incidents to the Help Desk because the steps didn't work. Investigation confirmed KB-00441 still references the legacy ADP payroll portal (used before the SF ECP migration in Q2 2025). Employees following the article were navigating to the decommissioned ADP portal instead of SF EC.

## Root Cause

Knowledge Base article KB-00441 was published during the legacy payroll environment and was not updated when Meridian migrated to SF ECP in Q2 2025. The KB governance process does not include a mandatory review trigger when a system is decommissioned or replaced. The article had a "Last Reviewed" date of 2022 and no owner assigned.

## Workaround

Employees directed to the correct process via `accessing-pay-statements.md` (SF EC → Pay → Pay Statements).

## Resolution

Payroll Ops rewrote KB-00441 to reflect the SF ECP process. Old ADP instructions removed. Article republished with a new "Last Reviewed" date and Payroll Ops assigned as article owner.

ServiceNow admin added a quarterly KB article review task to the Payroll Ops team queue. Articles without review in 12 months are auto-flagged in ServiceNow as "Potentially Outdated."

## Related

- ServiceNow KB: KB-00441 (updated — now reflects SF ECP process)
- `accessing-pay-statements.md` — primary self-service reference for pay statement access
- ADP portal (`adp.meridian-hr.internal`) decommissioned 2025-06-01
