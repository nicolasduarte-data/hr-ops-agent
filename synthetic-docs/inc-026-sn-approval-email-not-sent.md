# INC-0071334 — ServiceNow Approval Email Not Sent to Manager

**system_affected**: ServiceNow_ITSM
**resolution_status**: resolved
**reported_date**: 2025-09-16
**resolved_date**: 2025-09-17
**ticket_type**: incident
**reported_by**: IT Operations

## Description

Three separate RITM requests requiring manager approval (RITMs: 0092441, 0092488, 0092512) did not generate approval email notifications. The approvers were not notified, and the requests aged past SLA. All three affected RITMs were submitted by employees in the Marketing department.

## Root Cause

ServiceNow email notifications are controlled by the Notification Engine. Investigation found a notification configuration rule for "RITM Approval Request" was filtering by department — an overly specific filter (Department = "Sales") was inadvertently applied to the approval email notification. The filter was added 3 weeks prior during a customization for a Sales-specific workflow, and incorrectly replaced the default global condition.

Marketing employees' RITMs triggered the approval workflow but the notification was filtered out because the requesting employee's department did not match "Sales."

## Workaround

IT Operations manually sent email notifications to the affected managers. Managers approved the RITMs directly in ServiceNow via the approval link included in the manually sent email.

## Resolution

ServiceNow admin corrected the notification filter: removed the `Department = Sales` condition and restored the default global condition (all requests requiring approval). Validated by submitting test RITMs from multiple departments — all generated approval emails correctly.

## Related

- ServiceNow Notification Engine: RITM Approval Request notification
- Any notification customization should be scoped with explicit conditions — default conditions must not be overwritten
