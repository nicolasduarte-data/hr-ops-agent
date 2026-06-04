# INC-0071201 — ServiceNow RITM Routed to Wrong Team

**system_affected**: ServiceNow_ITSM
**resolution_status**: resolved
**reported_date**: 2025-10-29
**resolved_date**: 2025-10-30
**ticket_type**: incident
**reported_by**: HR Operations

## Description

An employee submitted a ServiceNow catalog request for "New Software Access — Workday Analytics" (RITM-0094422). The RITM was auto-routed to the IT Help Desk general queue rather than the Integration team queue, which owns Workday access provisioning. The Help Desk did not have the skills to fulfill the request and it aged for 4 days without action before HR Ops noticed.

## Root Cause

The ServiceNow catalog item "New Software Access — Workday Analytics" had an incorrect fulfillment group configured. The catalog item's `Assignment Group` field was set to `IT Help Desk` rather than `Integration Team`. The original catalog item was set up 8 months ago when Workday Analytics was a new tool; the assignment group was a placeholder that was never updated.

## Workaround

Help Desk manually reassigned the RITM to the Integration team. Integration team fulfilled the access request.

## Resolution

ServiceNow admin corrected the `Assignment Group` on the "New Software Access — Workday Analytics" catalog item to `Integration Team`. RITM routing audit scheduled: ServiceNow admin will review all catalog items annually for correct assignment group.

## Related

- ServiceNow ITSM: RITM routing is controlled by catalog item `Assignment Group` field
- Any new catalog item should have its assignment group verified with the owning team before publishing
