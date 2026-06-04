# INC-0071891 — Okta Attributes Not Updated After Azure AD Profile Change

**system_affected**: Okta_SSO
**resolution_status**: resolved
**reported_date**: 2025-11-25
**resolved_date**: 2025-11-26
**ticket_type**: incident
**reported_by**: HRIS Team

## Description

An employee who had a legal name change (processed in SF EC and manually updated in Azure AD by HR Ops on 2025-11-24) still shows the old name in all Okta-SSO-connected applications (SF EC app tile, ServiceNow, Concur) as of 2025-11-25 — more than 24 hours after the Azure AD update. The employee's display name in Okta itself shows correctly (new name), but the SSO profile attributes passed to connected apps still carry the old name.

## Root Cause

Okta profiles are synced from Azure AD via the Okta Azure AD integration (Okta Universal Directory → Azure AD mastered attributes). The attribute sync runs every 4 hours and correctly updated the Okta profile display name. However, the attribute mapping for the applications uses a **JIT (Just-in-Time) provisioning** model — the connected apps only receive updated profile attributes when the user next logs into that app via SSO. Since the employee had not logged out and back into SF EC, ServiceNow, or Concur since the name change, those apps had not received the updated name attribute.

## Workaround

IAM team manually triggered a re-provisioning push to the affected apps from Okta Admin:
- Okta Admin → Directory → People → [Employee] → Applications → Force Sync for each affected app.

Employee name updated in all three apps within 5 minutes.

## Resolution

Manual push applied. IAM documented that JIT-provisioned apps require either a force sync or a fresh SSO login to pick up profile attribute changes. Name change SOP updated: after legal name change in Azure AD, IAM will force-sync Okta provisioning for the employee's assigned apps as part of the standard process.

## Related

- Okta Universal Directory: Azure AD mastered attributes, 4-hour sync interval
- JIT provisioning: apps only receive updated attributes on next SSO login — force sync is the override
- Known-issues.md ISSUE-001 (SSO session handling post-password-reset — same Okta/Azure AD domain)
