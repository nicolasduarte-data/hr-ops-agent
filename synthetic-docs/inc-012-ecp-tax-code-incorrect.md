# INC-0070388 — ECP Tax Withholding Using Wrong State

**system_affected**: SuccessFactors_ECP
**resolution_status**: resolved
**reported_date**: 2025-10-08
**resolved_date**: 2025-10-10
**ticket_type**: incident
**reported_by**: Employee self-reported via HR Ops

## Description

Employee (ID: MRD-3344) relocated from Illinois to Texas in September 2025 and updated their home address in SF EC. However, their October 8 pay statement shows Illinois state income tax (IL SIT) still being withheld. Texas has no state income tax. The employee is over-withheld and requires a correction.

## Root Cause

In SF ECP, tax withholding state is determined by the **Work Tax Area** on infotype IT0207 (Residence Tax Area) and IT0208 (Work Tax Area), not by the home address in EC. When the employee updated their home address in EC, the change replicated to ECP and updated the residence address — but did not trigger an automatic update to IT0207/IT0208.

The payroll team must manually update the ECP tax area infotypes when an employee moves to a different tax state. This is a documented limitation of the EC→ECP integration: address changes do not cascade to tax configuration.

## Workaround

Payroll Ops corrected IT0207 and IT0208 in ECP to reflect Texas (tax area: TX-NONE — no state income tax). The correction is effective retroactively from the relocation date (2025-09-15). ECP will calculate a credit for over-withheld IL tax in the next regular payroll run.

## Resolution

Tax areas corrected in ECP. Employee received a credit in the 2025-10-25 payroll. Payroll Ops documented the manual step in the employee relocation SOP: "Address change in EC does not auto-update ECP tax areas — Payroll Ops must update IT0207/IT0208 manually."

## Related

- ECP infotypes: IT0207 (Residence Tax Area), IT0208 (Work Tax Area)
- EC→ECP integration: address replication does NOT cascade to tax configuration (known limitation)
- Employees relocating across state lines must notify Payroll Ops in addition to updating address in EC
