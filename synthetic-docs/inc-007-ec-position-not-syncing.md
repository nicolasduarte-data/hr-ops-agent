# INC-0070034 — EC Position Not Syncing After Promotion

**system_affected**: SuccessFactors_EC
**resolution_status**: resolved
**reported_date**: 2025-11-04
**resolved_date**: 2025-11-06
**ticket_type**: incident
**reported_by**: Maria Santos (HR Operations)

## Description

After completing a promotion workflow in SF Employee Central (EC), the employee's new position title and job code are visible in EC but have not replicated to the Workday tenant (subsidiary). The employee's manager in Workday still shows the old job code. The integration team confirmed the CPI iFlow ran without error, but the position object was not included in the delta payload.

## Root Cause

The position change triggered the Employee Central `Position Change` business process, but the CPI integration delta is configured to watch for changes to the `Employment` object, not the `Position` object. When a position is changed without a simultaneous employment record change, the CPI delta payload is empty. This is a known misconfiguration in the CPI integration mapping — SF support case INC-SF-4421 is open.

## Workaround

HRIS team can manually trigger a full-sync for the affected employee via the CPI integration monitoring console:
1. Log into SAP CPI (`cpi.meridian-hr.internal`).
2. Navigate to Monitor → Message Processing → Integration Flow: `EC-to-Workday-Employee-Delta`.
3. Use the manual trigger with the employee's EC person ID.
4. Allow 2 hours for Workday to process the update.

## Resolution

Short-term: manual full-sync applied (see workaround). Long-term: HRIS team updated the CPI iFlow delta configuration to also watch the `Position` object. Deployed to production 2025-11-06. Validated against 3 subsequent promotion transactions — all replicated correctly.

## Related

- INC-0060021 (EC→Workday replication delay — prior integration incident)
- Known-issues.md ISSUE-002 (EC→ECP replication lag)
