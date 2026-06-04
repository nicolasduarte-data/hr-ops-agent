# INC-0070089 — EC Workflow Approval Stuck — Approver Inbox Empty

**system_affected**: SuccessFactors_EC
**resolution_status**: resolved
**reported_date**: 2025-10-15
**resolved_date**: 2025-10-16
**ticket_type**: incident
**reported_by**: James Okafor (People Services)

## Description

A leave of absence workflow initiated for employee (ID: MRD-4412) is showing status "Pending Approval" in SF EC for 4 days. The designated approver (HR Manager, role: `HR_MANAGER_APPROVER`) confirmed their EC inbox is empty — the approval task is not appearing. The workflow is not progressing and no escalation has fired.

## Root Cause

Investigation in EC → Admin Center → Workflow Configuration revealed the approver rule for the LOA business process was configured with an `AND` condition requiring two role assignments: `HR_MANAGER_APPROVER` AND `LOA_ADMINISTRATOR`. The approver has `HR_MANAGER_APPROVER` but not `LOA_ADMINISTRATOR`, causing the workflow routing to find no eligible approver. The task was silently dropped rather than raising an error — this is the expected EC behavior when no approver is resolved.

## Workaround

HRIS admin can re-route the workflow:
1. In EC Admin Center → Manage Business Processes → locate the stuck workflow by employee ID.
2. Use **Reroute** action to assign the approval task directly to the backup HR Manager (`hrbp-backup@meridian-hr.internal`).
3. Approver completes the task from their inbox.

## Resolution

Workaround applied for the immediate case. HRIS team corrected the LOA business process approver condition from `AND` to `OR` to allow either role. Change validated in test tenant before production deployment. Deployed 2025-10-16.

## Related

- Known-issues.md ISSUE-005 (new-hire provisioning workflow routing failure — same root pattern)
- EC Admin: Business Process Configuration → LOA_APPROVAL_BP
