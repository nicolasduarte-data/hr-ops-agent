# INC-0071089 — Workday→ServiceNow Sync Delayed — New Hire Not in ITSM Directory

**system_affected**: Workday_Integration
**resolution_status**: resolved
**reported_date**: 2025-11-18
**resolved_date**: 2025-11-19
**ticket_type**: incident
**reported_by**: IT Operations (via HR Ops)

## Description

A new hire in the Workday subsidiary tenant (WD-5201, start date 2025-11-17) is not visible in the ServiceNow CMDB/People Directory 24 hours after their start date. IT Operations cannot look up the employee in ServiceNow to assign equipment, and the employee cannot submit ITSM tickets because their ServiceNow user account has not been provisioned.

## Root Cause

The Workday→ServiceNow sync uses a Workday Studio integration that exports worker data via REST API to ServiceNow's HR Service Delivery (HRSD) integration table. The integration runs every 6 hours. Investigation found the sync job ran at 06:00 on 2025-11-17 (before the employee's hire date effective time), and the 12:00 run was blocked by a Workday tenant maintenance window (scheduled 11:00–13:00 on 2025-11-17). The 18:00 run completed but the ServiceNow-side import job failed due to a missing required field (`cost_center`) — the employee's cost center was not yet populated in Workday at their hire date.

Two failures in sequence caused the 24-hour gap.

## Workaround

Integration team manually ran the Workday export for the affected worker and corrected the missing cost_center field in Workday. Manually triggered the ServiceNow import. Employee's user account provisioned by 10:00 on 2025-11-19.

## Resolution

Cost center field verified as required for ServiceNow import — Workday onboarding business process updated to enforce cost_center population before hire date effective time. Integration team will monitor for future maintenance-window conflicts that cause sync gaps.

## Related

- Workday Studio integration: `WD-to-ServiceNow-Worker-Sync`
- ServiceNow: HRSD integration table → User provisioning flow
- Maintenance windows for Workday tenant should be communicated to Integration team in advance
