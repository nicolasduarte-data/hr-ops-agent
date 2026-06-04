# Meridian HR Systems — Known Issues Register
**Last updated:** 2025-12-01 | **Owned by:** HRIS & IAM Teams | **Source system:** ServiceNow ITSM

---

## ISSUE-001 — SSO Login Loop After Password Reset
**System:** Workday / Okta
**Status:** Open (workaround available)
**Ticket ref:** INC0042811
**Reported:** 2025-09-14

**Symptom:** After resetting an Okta password via the self-service portal, Workday redirects back to the Okta login screen in a continuous loop. The user cannot reach their Workday home page.

**Root cause (under investigation):** Stale Okta session cookie not cleared on password reset. The SSO assertion is generated before the new credential propagates to the Workday SP metadata cache.

**Workaround:**
1. Clear all browser cookies and cache (Ctrl+Shift+Del → All time → Cookies)
2. Open Workday in a fresh private/incognito window
3. Log in with the new Okta password — SSO redirect succeeds on first attempt in a clean session
4. If still looping after two attempts, contact IAM: iam-support@meridian.com or ServiceNow queue *Access & Identity*

**Escalation:** IAM team owns Okta configuration. Contact via ServiceNow → *Access & Identity* queue or Slack #it-access for urgent cases.

---

## ISSUE-002 — EC Effective-Dated Change Not Replicating to Payroll
**System:** SAP SuccessFactors Employee Central → Employee Central Payroll (ECP)
**Status:** In Progress (partial fix deployed 2025-10)
**Ticket ref:** INC0039204
**Reported:** 2025-07-22

**Symptom:** An effective-dated change in EC (e.g., compensation change, job change, org reassignment) does not appear in the next payroll run. ECP retains the prior value.

**Root cause:** The EC→ECP integration (CPI iFlow) processes replication events in a nightly batch. If an effective date is set for a date that has already passed when the record is saved, the CPI iFlow may skip it as a "historical" record under certain conditions.

**Workaround:**
1. Do not use past effective dates for payroll-impacting changes unless explicitly required
2. After saving a compensation or job change, verify replication: EC → employee record → *Integration Events* tab → confirm event status = *Sent*
3. If the event status is *Failed* or *Pending* for >24 hours, raise a ServiceNow ticket (category: *EC-ECP Replication*) and tag the Integration team (RITM assignment: *Integration Support*)

**Escalation:** Integration team (CPI iFlows). Not HR Operations. ServiceNow → *Integration Support* queue.

---

## ISSUE-003 — Concur Receipt OCR Fails on Mobile Upload
**System:** SAP Concur
**Status:** Open
**Ticket ref:** INC0044517
**Reported:** 2025-11-03

**Symptom:** Using the SAP Concur mobile app (iOS and Android) to photograph a receipt, the OCR fails to extract vendor name, amount, or date. The fields remain blank, requiring manual entry.

**Root cause:** Concur OCR engine requires minimum 300dpi resolution. Mobile camera compression under certain lighting and background conditions drops below this threshold.

**Workaround:**
1. Place receipt flat on a high-contrast surface (white paper or desk)
2. Ensure adequate lighting — avoid shadows
3. If OCR still fails: scan the receipt and upload as a PDF from the desktop app (concur.meridian.com)
4. Manual entry is always accepted if OCR cannot be corrected

**Escalation:** SAP Concur support (internal request via ServiceNow → *Finance Systems → Concur*). Attach the receipt image and mobile device model.

---

## ISSUE-004 — Provisioning Ticket Not Auto-Created for New Hire
**System:** SAP SuccessFactors Onboarding 2.0 (ONB) → ServiceNow
**Status:** Open
**Ticket ref:** INC0041102
**Reported:** 2025-08-30

**Symptom:** After a new hire is confirmed in SF Recruiting (RCM) and transitions to ONB, the expected ServiceNow RITM for IT provisioning (laptop + accounts) is not automatically created. IT is unaware of the new hire until manually notified.

**Root cause (under investigation):** The ONB→ServiceNow integration webhook requires the *Requisition Business Unit* field to be populated in RCM at time of offer acceptance. Missing value causes the event to fail silently.

**Workaround:**
1. Recruiting coordinator: verify *Business Unit* is set on the requisition before extending an offer
2. If a provisioning RITM is missing within 24 hours of Day 0 creation in ONB: manually create a ServiceNow RITM (template: *New Employee IT Setup*) and assign to IAM queue
3. Alert the HRIS team (hris-support@meridian.com) so they can log the integration event failure

**Escalation:** HRIS team (ONB configuration) and Integration team (webhook). Not IT alone.

---

## ISSUE-005 — New-Hire Azure AD Account Not Provisioned
**System:** SAP SuccessFactors ONB → Azure AD (via Okta provisioning connector)
**Status:** In Progress
**Ticket ref:** INC0043888
**Reported:** 2025-10-15

**Symptom:** New hire arrives on Day 1 but has no Azure AD account (cannot log into Microsoft 365, Teams, SharePoint). The ServiceNow provisioning RITM was created correctly (ISSUE-004 not present), but the Okta→Azure AD sync did not run.

**Root cause:** Okta provisioning connector has a sync job that runs every 4 hours. If the RITM was completed within the same day as Day 1, and the sync cycle had not yet run, the AD account is not ready by 9am.

**Workaround:**
1. IT/IAM: manually trigger an Okta→Azure AD sync from the Okta admin console (Provisioning → Force Sync) after confirming the user exists in Okta
2. In urgent cases, create the AD account manually and link to the Okta user profile
3. New hire: use mobile hotspot + Workday mobile app for Day 1 essentials while AD sync resolves

**Escalation:** IAM team → Okta admin. P1 SLA applies if new hire cannot work on Day 1.

---

## ISSUE-006 — SAP PA30 Transaction Locked by Another User
**System:** SAP HCM (legacy HR module, used for Meridian subsidiary on-prem SAP)
**Status:** Open (expected: resolved with full migration Q3 2026)
**Ticket ref:** INC0040055
**Reported:** 2025-08-01

**Symptom:** When opening an employee record in transaction PA30 (Maintain HR Master Data), user receives error: *"Record is currently locked by user [USERID]. Try again later."* The lock persists even after the other user logs out.

**Root cause:** SAP dialog locks are not released automatically when a session is disconnected abnormally (browser close, network loss). The enqueue server holds the lock until the session timeout (default: 600 seconds, configurable).

**Workaround:**
1. Wait 10 minutes and retry — most locks release within the session timeout
2. If urgent: ask the locking user (shown in the error) to log out cleanly via SAP menu → *System → Log Off*
3. If the locking user is unknown or unavailable: raise a ServiceNow ticket (category: *SAP Basis → Lock Administration*). SAP Basis can release the enqueue lock manually via SM12

**Escalation:** SAP Basis team. Not HR Operations. ServiceNow → *SAP Basis* queue.

---

## ISSUE-007 — Workday EIB Load Failure — Supervisory Org Validation
**System:** Workday (Enterprise Interface Builder — EIB)
**Status:** Recurring (known pattern)
**Ticket ref:** Multiple — most recent INC0045201
**Reported:** Ongoing

**Symptom:** Mass-upload via Workday EIB (used by HR Ops for bulk org changes) fails with validation error: *"Supervisory Organization does not exist or is inactive."*

**Root cause:** The EIB template references supervisory org IDs (Workday internal reference IDs) that have been reorganized or inactivated since the template was last used. Workday does not warn at template creation — only at load time.

**Workaround:**
1. Before each EIB load, export the current active supervisory org list from Workday: *Reports → All Active Supervisory Organizations*
2. Cross-reference your upload template against the current list; update any stale org IDs
3. Use Workday Studio (or request Integration team assistance) to validate the EIB file against a sandbox tenant first

**Escalation:** Integration team for EIB template issues; HR Ops team lead for org structure questions. ServiceNow → *Integration Support* (EIB).
