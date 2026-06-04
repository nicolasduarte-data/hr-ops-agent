# Meridian IT Escalation Matrix
**Last updated:** 2025-11-20 | **Owned by:** IT Operations | **System:** ServiceNow ITSM

Use this matrix to route issues to the correct team and understand SLAs before submitting a
ServiceNow ticket. Priority is set at submission and affects response SLA.

---

## Priority definitions

| Priority | Definition | Examples |
|---|---|---|
| **P1 — Critical** | Business-stopping for a group or individual; no workaround | New hire cannot work on Day 1; payroll run blocked; SSO down for department |
| **P2 — High** | Significant impact; workaround available but painful | Replication failure affecting upcoming payroll; EIB load blocking org change |
| **P3 — Medium** | Standard issue; workaround available; not time-critical | OCR failure on expense receipt; PA30 lock; access request for existing employee |
| **P4 — Low** | Informational, enhancement, or cosmetic | Report label wrong; documentation update; low-urgency access review |

---

## Escalation paths by team

### HRIS Team
**Queue:** ServiceNow → *HRIS Support*
**Email:** hris-support@meridian.com

| Priority | Response SLA | Resolution SLA | Contact method |
|---|---|---|---|
| P1 | 30 minutes | 4 hours | ServiceNow P1 + Slack #hris-alerts |
| P2 | 2 hours | 1 business day | ServiceNow |
| P3 | 1 business day | 3 business days | ServiceNow |
| P4 | 3 business days | Scheduled sprint | ServiceNow |

**Escalation chain:**
1. HRIS Support queue (first contact)
2. HRIS Team Lead (if P1 unresolved in 2 hours): contact via Slack #hris-team
3. Director of HR Technology (if P1 unresolved in 4 hours)

---

### IAM Team (Access & Identity)
**Queue:** ServiceNow → *Access & Identity*
**Email:** iam-support@meridian.com | **Slack:** #it-access

| Priority | Response SLA | Resolution SLA | Contact method |
|---|---|---|---|
| P1 | 15 minutes | 4 hours | ServiceNow P1 + Slack #it-access (24/7) |
| P2 | 1 hour | 4 business hours | ServiceNow |
| P3 | 4 business hours | 1 business day | ServiceNow |
| P4 | 2 business days | Scheduled sprint | ServiceNow |

**P1 examples (Day-1 provisioning failures):**
- New hire has no Azure AD / M365 access on start date
- Okta SSO is down for a department (>5 users affected)
- Privileged account compromised

**Escalation chain:**
1. ServiceNow → *Access & Identity* queue + Slack #it-access
2. IAM Lead (P1 unresolved in 1 hour): direct message via Slack
3. IT Director (P1 unresolved in 2 hours)

---

### Integration Team
**Queue:** ServiceNow → *Integration Support*
**Email:** integration-support@meridian.com

| Priority | Response SLA | Resolution SLA | Contact method |
|---|---|---|---|
| P1 | 30 minutes | 4 hours | ServiceNow P1 + PagerDuty (on-call) |
| P2 | 2 hours | 8 business hours | ServiceNow |
| P3 | 1 business day | 3 business days | ServiceNow |
| P4 | 3 business days | Scheduled sprint | ServiceNow |

**P1 triggers (Integration):**
- EC→ECP replication failure on a payroll-run day
- ONB→ServiceNow webhook completely down (all new hires unprovisioned)
- CPI iFlow certificate expiry blocking all SF integrations

**Escalation chain:**
1. ServiceNow → *Integration Support* queue
2. On-call Integration Engineer (P1): via PagerDuty (alert via ServiceNow P1 process)
3. Integration Lead → IT Director if unresolved in 4 hours

---

### Payroll Operations
**Queue:** ServiceNow → *Payroll*
**Email:** payroll@meridian.com

| Priority | Response SLA | Resolution SLA | Contact method |
|---|---|---|---|
| P1 (payroll-run day) | 15 minutes | Immediate escalation | ServiceNow P1 + direct call (number in Payroll team page) |
| P2 | 4 business hours | 2 business days | ServiceNow |
| P3 | 1 business day | 5 business days | ServiceNow |

**Pre-payroll correction cutoff:** All EC data corrections and off-cycle payment requests must be submitted **2 business days before** the payroll run date. Late corrections are processed in the next cycle.

**Payroll run schedule:** Bi-weekly, Fridays. 2025 schedule published on the HR intranet.

**Escalation chain:**
1. ServiceNow → *Payroll* queue
2. Payroll Manager (P1 on run day): direct call listed in ServiceNow Payroll team page
3. Director of Finance (payroll-blocking issue unresolved)

---

### SAP Support (SuccessFactors / SAP HCM)
**External escalation** via SAP for Me Launchpad (SAP support portal).

| Tier | Use | SLA |
|---|---|---|
| SF P1 (Product defect blocking production) | SAP for Me → create Incident, component HCM-SF-* | SAP committed response: 1 hour |
| SF P2 (Functional defect, workaround available) | SAP for Me → Incident | SAP committed response: 4 hours |
| SF community/how-to | SAP Community (community.sap.com) | No SLA — peer support |

**Internal first:** HRIS team triages all SF issues first. External SAP support is raised only when HRIS confirms it is a product defect, not a configuration issue.

---

### Workday Support
**External escalation** via Workday Community and named support contact.

- **Workday Community:** community.workday.com — search known issues and maintenance posts first
- **Named Support Contact:** Available for Production tenants via Workday's Tenant Management portal
- **Critical issues:** Workday support SLA for P1 = 1-hour response (tenant down or security incident)

**Internal first:** HRIS team triages. External Workday support raised only for confirmed product defects or tenant availability issues.

---

## How to submit a P1

1. Create ServiceNow incident — set Priority = **1 - Critical** at submission
2. Title must include: system name + symptom (e.g., "P1 — Workday SSO down — Paris office")
3. Notify the owning team directly: Slack channel (above) or email with [P1] subject prefix
4. Stay available — the team will contact you within the response SLA window
5. Do not close the incident until the root cause is documented
