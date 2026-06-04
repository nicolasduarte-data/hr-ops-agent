# INC-0070312 — ECP Payslip Not Generated for New Employee

**system_affected**: SuccessFactors_ECP
**resolution_status**: resolved
**reported_date**: 2025-11-17
**resolved_date**: 2025-11-19
**ticket_type**: incident
**reported_by**: Payroll Operations

## Description

A new hire (employee ID: MRD-5101, start date: 2025-11-03) did not receive a pay statement for the November 14 pay date. The employee's profile exists in SF EC and the ECP infotype records (IT0000, IT0001, IT0008) are visible in payroll. However, the employee was not included in the payroll run for the 2025-11-14 pay period.

## Root Cause

Investigation in SF ECP payroll journal (transaction PA03) revealed the employee's payroll area was set to `US-BIWEEKLY-02` (which runs on a different cycle start date) instead of `US-BIWEEKLY-01` (the standard cycle). The hire workflow in SF EC copies the payroll area from the position's default — the position was created with the wrong payroll area, and this was inherited by the employee record.

ECP infotype IT0001 (Org Assignment) confirmed the wrong payroll area. This caused the employee to be included in the next cycle (Nov 28 pay date) rather than the Nov 14 run.

## Workaround

Payroll Ops ran an off-cycle payroll for the employee to cover the Nov 14 pay period. Off-cycle processing was completed via ECP transaction PA51 (Payroll Driver, off-cycle run). Employee received payment on 2025-11-19.

## Resolution

HRIS corrected the position's default payroll area in EC. Employee's IT0001 updated to `US-BIWEEKLY-01`. Validated in the Nov 28 regular payroll run — employee included correctly. Position template corrected to prevent recurrence.

## Related

- ECP transactions: PA03 (Payroll Status), IT0001 (Org Assignment), PA51 (Off-Cycle Payroll)
- Payroll Ops should verify payroll area on all new hires at onboarding stage
