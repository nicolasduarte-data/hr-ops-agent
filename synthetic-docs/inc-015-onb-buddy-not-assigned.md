# INC-0070578 — Onboarding Buddy Not Assigned in SF ONB

**system_affected**: SuccessFactors_ONB
**resolution_status**: resolved
**reported_date**: 2025-11-24
**resolved_date**: 2025-11-25
**ticket_type**: incident
**reported_by**: HR Operations

## Description

Two new hires starting on 2025-12-01 do not have an Onboarding Buddy assigned in SF ONB 2.0. The hiring managers confirmed they selected buddies in the manager onboarding wizard, but the buddy names are not appearing on the new hires' ONB dashboard or in the buddy welcome email workflow.

## Root Cause

SF ONB 2.0 buddy assignment uses a separate process step that requires the assigned buddy to have a valid SF EC user account AND an active `ONB_BUDDY` permission role. Both intended buddies (MRD-2210, MRD-3341) have SF EC accounts but were not granted the `ONB_BUDDY` role in RBP. When the manager selected the buddy in the wizard, the system accepted the selection but the buddy notification email and dashboard tile could not render because the role check failed silently at delivery time.

## Workaround

HRIS granted the `ONB_BUDDY` role to both employees via EC Admin Center → Role-Based Permissions → Permission Groups → ONB_BUDDY_GROUP. After adding both employees to the group, HRIS re-triggered the buddy assignment workflow from the ONB Admin dashboard.

Buddy confirmation appeared in both new hires' portals within 30 minutes.

## Resolution

Immediate fix applied. HRIS updated the buddy pool governance: all employees in the approved buddy list must be added to the `ONB_BUDDY_GROUP` before being selectable in the manager wizard. HR Operations maintains the buddy pool list and will audit the RBP group quarterly.

## Related

- SF ONB RBP: `ONB_BUDDY_GROUP` permission group
- Buddy program governance: HR Operations (`hr-ops@meridian-hr.internal`)
