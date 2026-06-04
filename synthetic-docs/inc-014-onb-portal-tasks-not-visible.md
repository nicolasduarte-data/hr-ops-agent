# INC-0070512 — SF Onboarding Portal Tasks Not Visible to New Hire

**system_affected**: SuccessFactors_ONB
**resolution_status**: resolved
**reported_date**: 2025-12-09
**resolved_date**: 2025-12-10
**ticket_type**: incident
**reported_by**: Talent Acquisition (on behalf of new hire)

## Description

A new hire (start date: 2025-12-16, employee ID: MRD-5210) reports that when logging into the SF Onboarding (ONB 2.0) portal at `onboarding.meridian-hr.internal`, they see a blank task panel — no activities, no compliance forms, no equipment requests. The welcome tile displays correctly but all task categories are empty.

This was reported on their 7th day of pre-boarding access (access provisioned 2025-12-09).

## Root Cause

Investigation in SF ONB Admin → Onboarding Dashboard → Employee Status showed the employee's ONB process was initiated but the task assignment step failed silently. The failure trace in Process Variant logs indicated the employee's `Hire Date` in EC was populated with the wrong format (MM/DD/YYYY instead of YYYY-MM-DD) due to a data entry error in the recruiting-to-onboarding handoff. SF ONB task assignment requires an ISO date format for the hire date field; the malformed date caused the task generation step to be skipped without raising a visible error.

## Workaround

HRIS corrected the hire date format in EC. SF ONB re-triggered the task assignment:
1. HRIS updated the hire date in EC (Job Information) to the correct ISO format.
2. In SF ONB Admin, used **Restart Process** on the employee's ONB record.
3. Tasks appeared in the new hire's portal within 15 minutes.

## Resolution

Process restarted and all tasks confirmed visible. New hire completed I-9 and equipment request tasks on 2025-12-10. No delay to start date.

Onboarding team updated the data entry SOP to enforce YYYY-MM-DD format when populating hire dates during the Recruiting→Onboarding handoff.

## Related

- Known-issues.md ISSUE-005 (new-hire account not provisioned — related provisioning failure)
- SF ONB Admin → Process Variant Logs for diagnostic trace
