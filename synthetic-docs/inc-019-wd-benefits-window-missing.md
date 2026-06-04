# INC-0070818 — Workday Benefits Enrollment Window Not Appearing for Subsidiary Employee

**system_affected**: Workday_HCM
**resolution_status**: resolved
**reported_date**: 2025-10-16
**resolved_date**: 2025-10-17
**ticket_type**: incident
**reported_by**: Employee via manager

## Description

During the annual Open Enrollment window (October 15 – November 1), a subsidiary employee (Workday ID: WD-4421) does not see the Open Enrollment task in their Workday inbox or any enrollment option under **Benefits**. Other colleagues in the same subsidiary tenant are seeing the enrollment task correctly.

## Root Cause

Workday Open Enrollment event windows are configured per **Benefit Group**. The affected employee's Benefit Group assignment was inadvertently removed during a data correction in August — the employee's benefits eligibility record shows `Benefit Group: [Blank]`. Without a Benefit Group assignment, Workday does not generate the OE event task for the employee.

The Benefit Group field is a required field, but the blank state was not caught by a validation rule at the time of the data correction.

## Workaround

Workday Benefits Administrator assigned the correct Benefit Group (`MERIDIAN-SUBSIDIARY-BENEFITS-US`) to the employee's eligibility record. After the assignment, a manual **Open Enrollment Event** was created for the employee via Workday: Benefits → Create Enrollment Event → Open Enrollment.

The employee's OE task appeared in inbox within 5 minutes.

## Resolution

Benefit Group corrected. Employee completed enrollment before the November 1 deadline. Workday team added a validation report: run weekly during OE window to flag any employee with a blank Benefit Group.

## Related

- Workday Benefits configuration: Benefit Groups define OE eligibility
- Subsidiary employees use a separate Benefit Group from primary Meridian employees
