# INC-0071267 — ServiceNow HRSD Case Not Created After Form Submission

**system_affected**: ServiceNow_HRSD
**resolution_status**: resolved
**reported_date**: 2025-11-05
**resolved_date**: 2025-11-06
**ticket_type**: incident
**reported_by**: Employee self-reported

## Description

An employee submitted a personal data change request via the ServiceNow HR Service Delivery portal (catalog item: "Employee Records — Personal Data Change Request") and received a confirmation email with case number HR-0041230. When the employee followed up 5 days later, HR Operations could not locate the case — it was not in the HRSD queue, and the case number did not resolve in ServiceNow search.

## Root Cause

Investigation in ServiceNow revealed the case was created successfully on the HRSD side but was immediately placed in "Draft" state due to a validation rule that requires the requesting employee to have a valid HR profile in the HRSD People directory. The employee had recently been rehired (6 weeks prior) and their old HRSD People record was in "Inactive" state rather than "Active." The case creation flow does not surface a visible error when it hits this state — it silently moves the case to Draft and the confirmation email still sends (the email fires on form submission, before the state check).

The case was sitting in Draft state, invisible to the HR Operations queue, for 5 days.

## Workaround

ServiceNow admin activated the employee's HRSD People record. The Draft case was manually moved to "Open" state and assigned to HR Operations. HR Ops processed the request.

## Resolution

Immediate: case processed. Long-term: ServiceNow admin updated the HRSD catalog item validation rule to surface an explicit error to the submitter (rather than silently creating a Draft case) when the requesting employee's People record is inactive. HR Ops also added a step to the rehire onboarding checklist: activate rehired employee's HRSD People record before their start date.

## Related

- ServiceNow HRSD: People directory → record status must be Active for HRSD case creation
- Rehire onboarding checklist: `onboarding-checklist.md`
