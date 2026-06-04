# Meridian New-Hire Onboarding Checklist
**Last updated:** 2025-11-10 | **Owned by:** HR Operations | **System:** SF ONB / ServiceNow / Workday

This checklist covers all parties: HR, IT, Manager, and the new hire. It mirrors the
automated n8n onboarding workflow — any step listed as "automated" is triggered by the
new hire appearing in SF ONB with a confirmed start date.

---

## Before Day 1 (T-7 to T-1)

### HR Operations
- [ ] Confirm start date and role in SF Recruiting (RCM) — triggers ONB workflow
- [ ] Verify *Business Unit* field is populated in the RCM requisition (required for ServiceNow integration — see ISSUE-004)
- [ ] Confirm employment type: FTE, contractor, or intern (affects system access scope)
- [ ] Send pre-boarding email with ONB portal link (auto-sent by SF ONB on confirmation)

### Automated (SF ONB → ServiceNow)
- [ ] ServiceNow RITM auto-created: *New Employee IT Setup* (laptop + accounts) → IAM queue
- [ ] ServiceNow RITM auto-created: *Badge Access Request* → Facilities queue
- [ ] Okta user account pre-provisioned (via Okta→Azure AD connector, 4-hour sync cycle)

### New Hire
- [ ] Complete pre-boarding tasks in SF ONB portal:
  - Personal data (legal name, address, DOB, national ID)
  - Emergency contacts
  - Tax form (W-4 or equivalent)
  - Direct deposit setup (routed to ECP)
- [ ] Confirm equipment delivery address (if remote)

### Manager
- [ ] Prepare 30/60/90-day plan and share with new hire before Day 1
- [ ] Schedule team introduction meeting for Day 1
- [ ] Review access needs and confirm with HRIS if any non-standard system access is required
- [ ] Notify your EA / operations contact of the start date for badge and parking (if applicable)

---

## Day 1

### IT / IAM
- [ ] Confirm Azure AD account is active (verify Okta→AD sync has run — ISSUE-005 mitigation)
- [ ] Verify laptop is ready and joined to Azure AD; confirm M365 license assigned
- [ ] Send new hire a "Your accounts are ready" email with:
  - Okta login URL and MFA enrollment instructions
  - Workday URL
  - SuccessFactors self-service URL
  - ServiceNow helpdesk URL

### New Hire
- [ ] Log into Okta and enroll MFA (Okta Verify app)
- [ ] Confirm Workday access and review profile (verify personal data from pre-boarding is correct)
- [ ] Log into SuccessFactors Employee Central and confirm job information record
- [ ] Log into Microsoft 365 (email, Teams)
- [ ] Join team Slack workspace and relevant channels (list provided by manager)

### Manager
- [ ] Conduct team introduction meeting
- [ ] Walk through 30/60/90-day plan
- [ ] Confirm direct report is visible in Workday org chart (if not: contact HRIS)

---

## Week 1

### New Hire
- [ ] Complete mandatory compliance training in SF LMS (deadline: Day 30)
  - Courses: Information Security Awareness, Code of Conduct, Anti-Harassment, GDPR Basics
- [ ] Review IT Acceptable Use Policy (linked in the LMS course catalog)
- [ ] Set up SAP Concur profile (if role requires expense reporting):
  - Download Concur mobile app
  - Link cost center (ask manager)
  - Complete a test expense entry
- [ ] Review benefits elections in Workday (Benefits worklet) — confirm pre-populated elections or make changes during new-hire enrollment window (30 days from start date)

### HR Operations
- [ ] Confirm pre-boarding tasks completed in ONB portal
- [ ] Verify EC employee record is correct: position, grade, cost center, manager
- [ ] Close the ONB workflow in SF ONB after Week 1 completion

### Manager
- [ ] First 1:1 check-in: confirm access to all needed systems; raise any gaps to HRIS
- [ ] Verify direct report is enrolled in the correct Workday supervisory organization

---

## Day 30 checkpoint

- [ ] SF LMS compliance training completed (HR checks completion report)
- [ ] Benefits enrollment confirmed or deadline passed (HR sends reminder at Day 25)
- [ ] Any outstanding access requests resolved (manager confirms with HRIS)
- [ ] HRBP introduction meeting scheduled (for FTE hires in eligible bands)

---

## Common onboarding failure modes

| Symptom | Cause | First contact |
|---|---|---|
| No laptop on Day 1 | ServiceNow RITM not auto-created (ISSUE-004) | IAM + manually create RITM |
| No Azure AD / M365 access | Okta sync delay (ISSUE-005) | IAM → force Okta sync |
| Cannot log into Workday (SSO loop) | Post-password-reset Okta session issue (ISSUE-001) | Clear cookies → private window |
| ONB portal not accessible | Pre-boarding email link expired (links valid 7 days) | HR Operations → resend invite |
| LMS courses not assigned | New hire not in correct Learning Group in SF | HRIS Support |
| EC record not visible to manager | Supervisory org not set correctly | HRIS Support |
