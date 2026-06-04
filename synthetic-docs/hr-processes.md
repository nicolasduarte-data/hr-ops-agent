# Meridian HR Process Guide
**Last updated:** 2025-11-15 | **Owned by:** HR Operations | **System:** Multiple

---

## 1. Requesting Time Off (Workday)

Employees request PTO, sick leave, and LOA through Workday's **Time Off** worklet.

### Standard PTO / Sick Leave
1. Log into Workday → **Time Off** worklet → **Request**
2. Select absence type: *Vacation*, *Sick*, or *Personal Day*
3. Enter start and end dates; confirm day count
4. Submit — your direct manager receives an approval task in Workday
5. You receive an email notification when approved or declined
6. Approved time automatically updates your Workday balance and calendar

**SLA:** Manager approval within 2 business days for requests submitted ≥5 days in advance.

### Leave of Absence (LOA / FMLA)
FMLA requests require HR Business Partner involvement and are **not** submitted through the standard Time Off worklet.
1. Contact your HRBP or email hr-leaves@meridian.com
2. HRBP initiates the LOA business process (BP) in Workday
3. Employee receives Workday action items for supporting documentation
4. Payroll is notified automatically once the LOA is approved in Workday

**Note:** FMLA eligibility requires 12 months of employment and 1,250 hours worked in the prior year.

---

## 2. Updating Personal Data in SAP SuccessFactors Employee Central (EC)

Employees can update some personal data directly in EC; other changes require HR approval.

### Self-service changes (no approval required)
- Home address
- Emergency contact
- Bank account for payroll (ECP module — see §9)
- Personal email

**How:** Log into SuccessFactors → **Employee Profile** → **Personal Information** → **Edit**. Save triggers an effective-dated change record.

### HR-approval required changes
- Legal name change (requires documentation: marriage certificate, court order)
- Date of birth correction
- National ID / SSN correction

Submit a ServiceNow HR ticket (category: *Employee Data Correction*) and attach supporting documentation. HR Operations processes within 3 business days.

**Note on effective dates:** All EC data changes are effective-dated. If you set an effective date in the future, the change will not appear in payroll until that date is reached. Payroll replication from EC to ECP runs nightly.

---

## 3. New-Hire Onboarding — SAP SuccessFactors Onboarding 2.0 (ONB)

The onboarding process begins in SF ONB as soon as a hire is confirmed in Recruiting (RCM).

### Pre-boarding (before Day 1)
1. New hire receives an ONB welcome email with a portal link and temporary credentials
2. New hire completes pre-boarding tasks in the ONB portal: personal data entry, emergency contacts, tax forms, direct deposit (routed to ECP)
3. IT provisioning ticket is auto-created in ServiceNow (RITM) from ONB — triggers account creation in Azure AD and Workday (if the hire is in a Workday subsidiary)
4. Equipment request RITM is auto-created (laptop, badge) per role profile

### Day 1 tasks (manager and new hire)
- Manager completes: workstation setup, system access review, team introductions
- New hire completes: compliance training in SF LMS (mandatory — must be done in 30 days), review of IT Acceptable Use Policy

### Common onboarding issues
See `known-issues.md` for: provisioning ticket not auto-created; new-hire account not provisioned in Azure AD; ONB portal access error.

---

## 4. Benefits Open Enrollment (Workday)

Annual open enrollment runs in Workday each November for the following calendar year.

1. Watch for the company-wide enrollment announcement email (from Benefits Team)
2. Log into Workday → **Benefits** worklet → **Open Enrollment**
3. Review and confirm (or change) elections for: medical, dental, vision, FSA/HSA, life insurance
4. Dependents must be added in this window; no changes are allowed outside enrollment except qualifying life events (QLE)
5. Submit elections before the enrollment deadline (communicated by Benefits Team each year)

**Qualifying Life Events (QLE):** Marriage, birth/adoption, loss of other coverage. QLE changes must be submitted within 30 days of the event via Workday → Benefits → **Change Benefits for a Life Event**.

---

## 5. Submitting Expenses (SAP Concur)

Meridian uses SAP Concur for expense reporting.

1. Download the SAP Concur mobile app or log in at concur.meridian.com
2. Create an expense report: **Expense** → **Create New Report**
3. Add expense items; attach receipts (photo via mobile or PDF upload)
4. Select the appropriate cost center (check with your manager if unsure)
5. Submit to your direct manager for approval
6. Approved reports are processed by Finance; reimbursement appears in your next payroll cycle

**Receipt OCR note:** Mobile photo upload uses OCR to extract receipt data. Known issue: OCR fails on crumpled or low-contrast receipts. Workaround: photograph on a flat, contrasting surface, or upload a scanned PDF. See `known-issues.md` for the open ticket.

**Policy limits:** Meals ≤$75/person (business justification required above $50). No alcohol reimbursement. Hotels require pre-approval >$250/night.
