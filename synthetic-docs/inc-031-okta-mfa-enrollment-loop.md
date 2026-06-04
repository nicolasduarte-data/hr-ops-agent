# INC-0071701 — Okta MFA Enrollment Loop on First Login

**system_affected**: Okta_SSO
**resolution_status**: resolved
**reported_date**: 2025-12-08
**resolved_date**: 2025-12-09
**ticket_type**: incident
**reported_by**: IT Operations (new hire reported to manager)

## Description

A new hire (start date: 2025-12-08) is unable to complete Okta MFA enrollment. When logging into the Okta portal for the first time and following the MFA setup wizard (authenticator app enrollment), after scanning the QR code and entering the OTP, the page redirects back to the beginning of the MFA enrollment wizard instead of completing setup. The loop repeats indefinitely. Confirmed on both Chrome and Firefox.

## Root Cause

Okta MFA enrollment uses a session cookie to track progress through the enrollment wizard. Investigation in Okta System Log (Admin → Reports → System Log) showed the enrollment session was being created but immediately invalidated. The cause: the new hire's laptop had a browser extension ("Privacy Badger") that was blocking the Okta first-party session cookie (`sid`) due to a misconfigured content policy rule in the extension.

The extension blocked the cookie that carries the enrollment state between wizard steps, causing the wizard to reset on each OTP submission.

## Workaround

IT Operations instructed the employee to:
1. Disable the Privacy Badger extension (or any privacy/tracker-blocking extension) in browser settings.
2. Complete MFA enrollment in a clean browser profile or Incognito mode.
3. Re-enable the extension after successful enrollment.

Employee completed enrollment in 5 minutes after disabling the extension.

## Resolution

Okta MFA enrollment completed. IT Operations added a note to the new hire IT checklist: "If MFA enrollment fails or loops, disable browser extensions and retry in Incognito mode."

Long-term: IT is evaluating whether to add Okta's domains to the allowed-list in the company's standard browser extension policy.

## Related

- Okta System Log: `Admin → Reports → System Log` — use for diagnosing enrollment failures
- Known-issues.md ISSUE-001 (SSO login loop after password reset — different trigger, same Okta SSO domain)
