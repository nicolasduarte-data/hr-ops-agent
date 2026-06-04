# INC-0070201 — EC Role-Based Permissions (RBP) Blocking Manager Access

**system_affected**: SuccessFactors_EC
**resolution_status**: resolved
**reported_date**: 2025-09-22
**resolved_date**: 2025-09-23
**ticket_type**: incident
**reported_by**: Tom Halliwell (IT Operations)

## Description

A newly promoted manager (employee ID: MRD-2891) is unable to view or edit direct reports' employment records in SF EC. When navigating to a direct report's profile, she receives error: "You do not have permission to view this information (RBP-403)." Her direct reports are correctly assigned in the EC org structure — the issue is with RBP permission propagation.

## Root Cause

EC Role-Based Permissions (RBP) uses a dynamic group model — manager permissions are granted via a `Manager` target population rule that resolves based on the `Reports To` field. The promotion workflow updated the `Reports To` field on her direct reports' records with an effective date of 2025-09-22, but the RBP dynamic group cache had not yet refreshed. RBP group cache refresh runs every 4 hours in the Meridian EC tenant configuration.

The manager was granted access exactly at the effective date of her promotion, but the cache had not propagated.

## Workaround

Wait up to 4 hours for RBP cache to propagate. If urgent access is needed, HRIS can manually trigger a permission group recalculation:
- EC Admin Center → Permission Groups → [Manager Target Population] → Force Refresh.

## Resolution

HRIS triggered a manual RBP recalculation at 14:30 on 2025-09-22. Manager confirmed access restored at 14:45. No data integrity issue — access was a timing/cache issue only.

Long-term: HRIS is reviewing whether to reduce the RBP cache refresh interval from 4 hours to 1 hour for time-sensitive promotion scenarios. Pending capacity review with SAP.

## Related

- EC Admin Center → Permission Groups → Manager Target Population (dynamic rule configuration)
- Any manager promotion/transfer scenario may experience this 4-hour delay
