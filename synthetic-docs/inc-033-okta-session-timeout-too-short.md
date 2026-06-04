# INC-0071829 — Okta Session Timeout Too Short — Users Repeatedly Logged Out

**system_affected**: Okta_SSO
**resolution_status**: resolved
**reported_date**: 2025-08-19
**resolved_date**: 2025-08-21
**ticket_type**: incident
**reported_by**: HR Operations (multiple employee reports)

## Description

HR Operations received 8 employee complaints in the same week reporting that they are being logged out of all Meridian applications (SF EC, Workday, ServiceNow) every 30 minutes while actively working. Re-authentication via Okta is required each time, including MFA prompt. This is disruptive and is affecting productivity, particularly for employees running long payroll processes in ECP.

## Root Cause

Investigation in Okta Admin → Security → Authentication Policies → Global Session Policy revealed the session idle timeout was set to 30 minutes (down from the previous 2 hours). The change was made 10 days prior during a security review — a security analyst reduced the session idle timeout as a precautionary measure after an unrelated security audit recommendation, without first assessing the operational impact on long-running HR workflows.

Okta's "idle" timeout counts from the last user interaction with the Okta session — not from the last interaction with the application. Users working in a browser tab for more than 30 minutes without a navigation event that hits Okta were being silently timed out.

## Workaround

Users experiencing frequent logouts could extend their session by periodically clicking the Okta dashboard tile — this refreshes the session token. Not a practical long-term solution.

## Resolution

After cross-functional review (IT Security + HR Ops + Payroll), the idle session timeout was revised to 60 minutes (compromise between security posture and operational requirement for long-running payroll transactions). Maximum session lifetime retained at 12 hours (unchanged). Change documented in the Okta Security Configuration Change Log with stakeholder sign-off.

## Related

- Okta Admin: Security → Authentication Policies → Global Session Policy
- Security change management: session timeout changes require HR Ops and Payroll Ops review before deployment
