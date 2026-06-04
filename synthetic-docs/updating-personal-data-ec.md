# Updating Personal Data in Employee Central — Meridian HR Guide

**System**: SAP SuccessFactors Employee Central (EC)
**Applies to**: All employees
**Last updated**: 2026-01-20
**Owner**: HR Operations / HRIS Team

---

## Overview

Your personal data in SAP SuccessFactors Employee Central (SF EC) is the master record that flows to payroll, benefits, and identity management. Updates made here replicate downstream to SF Employee Central Payroll (ECP), Workday (subsidiary employees), and your Okta/Azure AD profile within 24–48 hours.

**Always update data in SF EC first.** Updating data directly in a downstream system (e.g., your Azure AD profile) will be overwritten by the next EC sync.

---

## What You Can Update Yourself (Employee Self-Service)

Employees can update the following without manager or HR approval:

| Field | Where in SF EC |
|---|---|
| Home address | My Profile → Personal Information → Address |
| Personal email | My Profile → Personal Information → Contact Information |
| Emergency contact | My Profile → Personal Information → Emergency Contacts |
| Preferred name / display name | My Profile → Personal Information → Name |
| Marital status | My Profile → Personal Information → Personal Details |
| Bank account for direct deposit | My Profile → Pay → Payment Information |

**Steps:**
1. Log into SF EC at `successfactors.meridian-hr.internal`.
2. Click your **profile photo** (top right) → **My Profile**, or use the Home screen tile.
3. Navigate to the relevant section using the left-hand menu.
4. Click **Edit** (pencil icon) next to the field you want to update.
5. Most personal data changes use **effective dating**: you will be asked to enter an **Effective Date** — use today's date unless the change is retroactive (retroactive changes require HR approval).
6. Enter the updated value and click **Save**.
7. Review the confirmation message. Changes requiring manager review enter a **workflow** — you will see the status "Pending Approval" until your manager or HR approves.

---

## What Requires HR or Manager Approval

The following changes route through a workflow and require HR approval:

- **Job title or department** — these are HR-managed fields; employees cannot edit directly
- **Work location** — requires manager and HRIS approval for RBP and office assignment
- **Legal name change** — requires documentation; contact HR Operations
- **Date of birth corrections** — requires HR and Payroll Ops review (payroll compliance)

To initiate these changes, submit a case via ServiceNow HR Service Delivery: **Employee Records → Personal Data Change Request**.

---

## Effective Dating in EC

SAP SuccessFactors stores most employment data as **effective-dated records**. This means every change creates a new record with an effective date rather than overwriting the previous value. This enables historical reporting and audit trails.

**Important:** If you enter the wrong effective date (e.g., a future date instead of today), your change will not be visible until that date. To correct a misdated entry, contact the HRIS team at `hris-support@meridian-hr.internal` — employees cannot delete historical records.

---

## Replication to Downstream Systems

| Downstream system | Replication frequency | Notes |
|---|---|---|
| SF ECP (Payroll) | Daily batch (overnight) | Bank detail changes take effect next pay period |
| Workday (subsidiary) | Every 4 hours via CPI integration | See ISSUE-002 (known-issues.md) for known replication delays |
| Okta / Azure AD | Within 1 hour via Okta Workflows | Profile sync; SSO-related attributes only |

If your change is not visible in a downstream system after 48 hours, raise a ServiceNow ITSM incident and assign to **Integration** team.

---

## Data Accuracy Notice

EC is the system of record. Inaccurate data in EC (wrong address, wrong bank account) affects payroll, benefits enrollment, and tax reporting. Employees are responsible for keeping their data current. Annual data audits are conducted by HR in Q1 — you may receive a task in your EC inbox to review and confirm your profile.

---

## Contact

- **Self-service questions**: `hr-ops@meridian-hr.internal`
- **HRIS / technical issues**: `hris-support@meridian-hr.internal`
- **Name/date of birth corrections**: HR Operations via ServiceNow HRSD case
