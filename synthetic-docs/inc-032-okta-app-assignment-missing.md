# INC-0071764 — Okta App Assignment Missing — Employee Cannot Access SF EC

**system_affected**: Okta_SSO
**resolution_status**: resolved
**reported_date**: 2025-10-27
**resolved_date**: 2025-10-27
**ticket_type**: incident
**reported_by**: Employee self-reported via IT Help Desk

## Description

An employee (ID: MRD-4501) transferred from the Workday subsidiary to the main Meridian entity effective 2025-10-20. After the transfer, the employee can log into the Okta portal but does not see the "SuccessFactors EC" tile — it is not assigned to their Okta profile. They can access Workday (subsidiary tenant) but not SF EC, preventing them from completing self-service HR tasks in the new entity.

## Root Cause

Okta application assignment is driven by Okta Group membership, which is provisioned via Azure AD group sync. The employee's entity transfer in SF EC updated their department and company code, which should have triggered an Azure AD group change (from `SUBSIDIARY_USERS` to `MERIDIAN_USERS`). However, the Azure AD group sync runs every 60 minutes and there is a propagation delay: the Okta group sync from Azure AD runs every 4 hours.

The SF EC application tile is assigned to members of the `MERIDIAN_USERS` Okta group. The employee was not in this group yet because the Azure AD → Okta sync had not yet propagated the group change (the employee accessed Okta within the 4-hour propagation window).

## Workaround

IAM team manually assigned the `SuccessFactors EC` Okta app to the employee's profile. Employee confirmed access within 2 minutes of the manual assignment.

## Resolution

Immediate access restored. No change to sync frequency — 4-hour propagation is expected behavior. IAM team added entity transfer to the list of events that trigger a manual Okta app review by the IT Help Desk (same-day review SLA).

## Related

- Okta Admin: App Assignments → SuccessFactors EC → assigned to group `MERIDIAN_USERS`
- Azure AD group sync to Okta: 4-hour propagation — manual override available via Okta Admin
