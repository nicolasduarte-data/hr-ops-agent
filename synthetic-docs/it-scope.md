# Meridian IT Team Scope & Responsibilities
**Last updated:** 2025-11-20 | **Owned by:** IT Operations | **System:** ServiceNow ITSM

This document defines ownership boundaries across Meridian's IT teams. Use it to route
ServiceNow tickets to the correct queue on first contact.

---

## 1. HRIS Team

**Systems owned:** SAP SuccessFactors (all modules: EC, ONB, PMGM, RCM, LMS, ECP),
SAP HCM (legacy on-prem, subsidiary), Workday configuration (Meridian main tenant)

**Responsibilities:**
- SuccessFactors configuration: role-based permissions (RBP), workflows, business rules
- SF data quality: effective-dated corrections, position management, org structure
- ONB portal setup and new-hire workflow configuration
- Workday business process (BP) configuration and tenant administration
- Annual SF/Workday release testing and rollout
- HR reporting (operational, non-BI)

**Does NOT handle:**
- Infrastructure or network issues affecting SF/Workday availability (→ Integration or Vendor Support)
- SAP Basis / landscape management (→ SAP Basis team)
- Payroll processing errors (→ Payroll Operations)
- Azure AD / Okta provisioning (→ IAM)
- End-user device or browser issues (→ IT Helpdesk)

**Contact:** hris-support@meridian.com | ServiceNow queue: *HRIS Support*

---

## 2. IAM Team (Identity & Access Management)

**Systems owned:** Okta (IdP), Azure Active Directory, SSO configuration for all applications,
Workday provisioning connector, SuccessFactors SSO, Microsoft 365

**Responsibilities:**
- User provisioning and deprovisioning (joiner/mover/leaver processes)
- Okta MFA enrollment and reset
- Azure AD account creation, license assignment, group membership
- SSO configuration for all SaaS applications
- Access certification campaigns (quarterly)
- Privileged access review

**Does NOT handle:**
- HRIS application configuration or HR data (→ HRIS)
- Exchange mailbox content or email routing rules (→ IT Helpdesk / M365 Admin)
- Application-level role assignments within SF/Workday (→ HRIS)
- Network or VPN (→ Network team)

**Contact:** iam-support@meridian.com | ServiceNow queue: *Access & Identity* | Slack: #it-access
**SLA:** Standard access requests: 1 business day. Day-1 provisioning failures: P1, 4-hour SLA.

---

## 3. Integration Team

**Systems owned:** SAP CPI (Cloud Platform Integration), Boomi middleware, Workday EIB (Enterprise Interface Builder), SuccessFactors→ECP replication iFlows, ONB→ServiceNow webhook, SF→Okta provisioning feed

**Responsibilities:**
- All data flows between HR systems (SF EC→ECP, SF ONB→ServiceNow, Workday→Azure AD)
- EIB template support and validation
- CPI iFlow monitoring, error triage, and incident resolution
- Boomi process design and support
- Integration-layer root cause analysis for cross-system data discrepancies
- New integration scoping and build (project work)

**Does NOT handle:**
- Source system configuration (→ HRIS for SF/Workday config)
- Destination system configuration (→ IAM for Azure AD/Okta, Payroll Ops for ECP)
- ServiceNow ITSM configuration (→ ServiceNow Admin)
- End-user data entry errors (→ HRIS or HR Operations)

**Contact:** integration-support@meridian.com | ServiceNow queue: *Integration Support*
**On-call:** Available for P1 integration failures outside business hours via PagerDuty (escalate through ServiceNow P1 process)

---

## 4. Payroll Operations

**Systems owned:** SAP Employee Central Payroll (ECP), payroll run schedule, tax configuration

**Responsibilities:**
- Payroll run processing (bi-weekly)
- Off-cycle payment requests
- Payroll reconciliation and audit
- W-2 / tax document distribution
- Payroll error corrections (overpay/underpay)
- ECP configuration for pay codes, deductions, and wage types

**Does NOT handle:**
- EC→ECP replication failures (→ Integration team for the iFlow; HRIS for EC data)
- Benefit deduction setup in Workday (→ HRIS)
- Compensation changes in EC (→ HRIS / HR Operations)

**Contact:** payroll@meridian.com | ServiceNow queue: *Payroll*
**SLA:** Pre-payroll corrections: 2 business days before payroll run date. Off-cycle payments: 5 business days.

---

## 5. ServiceNow Admin

**Systems owned:** ServiceNow ITSM platform (incident, request, change, problem management), HR Service Delivery (HRSD), catalog items, SLA definitions

**Responsibilities:**
- ServiceNow platform administration and upgrades
- Catalog item creation and maintenance
- Workflow and approval configuration within ServiceNow
- HRSD module configuration
- SLA monitoring and reporting
- Integration of ServiceNow with other ticketing or monitoring tools

**Does NOT handle:**
- The content or resolution of individual tickets (→ responsible team per category)
- HR policy decisions (→ HR Operations)
- Source system issues that feed ServiceNow data (→ HRIS, Integration, or IAM)

**Contact:** servicenow-admin@meridian.com | ServiceNow queue: *Platform Administration*

---

## Quick routing reference

| Issue type | First queue |
|---|---|
| SF/Workday configuration, RBP, business process | HRIS Support |
| Okta login, SSO loop, MFA reset | Access & Identity |
| Azure AD account, Microsoft 365 access | Access & Identity |
| New-hire provisioning failure (account/laptop) | Access & Identity |
| EC→ECP replication failure | Integration Support |
| EIB load error | Integration Support |
| ONB→ServiceNow webhook not firing | Integration Support |
| Payroll error, W-2 issue, off-cycle payment | Payroll |
| ServiceNow platform issue (portal, catalog) | Platform Administration |
| General IT (printer, VPN, hardware, browser) | IT Helpdesk |
