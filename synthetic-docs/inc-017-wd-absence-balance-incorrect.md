# INC-0070701 — Workday Absence Balance Shows Negative After Approved Request

**system_affected**: Workday_HCM
**resolution_status**: resolved
**reported_date**: 2025-10-21
**resolved_date**: 2025-10-22
**ticket_type**: incident
**reported_by**: Employee self-reported via manager

## Description

Employee (Workday ID: WD-7741) submitted a PTO request in Workday for November 3–7 (5 days). The request was approved by the manager. After approval, the employee's PTO balance in Workday shows -1.5 days. The employee's accrual rate should provide sufficient balance (they have 8 days accrued per their last statement).

## Root Cause

Workday absence balance calculations reflect both taken and **scheduled future time off** across the current accrual period. The employee had a previously approved absence request for October 28–29 that was showing in a "Pending Payroll" status (approved but not yet posted to the payroll period). Workday's balance display counts both confirmed future requests and pending-payroll requests against the current balance — the display looked like a negative because the two approved requests together exceeded the accrued balance shown at the current point in the accrual cycle.

The employee's actual accrued balance as of the November payroll posting date was sufficient to cover both requests.

## Workaround

Review the **full balance detail view** in Workday: Time Off → Balance → click "View Details" to see the breakdown of accruals, taken, and scheduled amounts. This provides the full picture vs. the simplified balance tile.

## Resolution

No data correction needed — the balance was accurate when viewed in full detail. HR Ops provided the employee with guidance on reading the balance detail view. Workday Help Center article shared: "Understanding Your Absence Balance in Workday."

## Related

- Workday accrual posting runs at the start of each pay period
- "Negative balance" displays are common when viewing mid-period before the next accrual posts
