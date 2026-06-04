# INC-0070451 — ECP Direct Deposit Not Updated After Bank Change in EC

**system_affected**: SuccessFactors_ECP
**resolution_status**: resolved
**reported_date**: 2026-01-06
**resolved_date**: 2026-01-07
**ticket_type**: incident
**reported_by**: HR Operations

## Description

Employee (ID: MRD-4788) updated their bank account for direct deposit in SF EC on 2026-01-03 (Profile → Pay → Payment Information). The January 10 payroll run used the old bank account. The employee's pay was deposited to a closed account and returned by the bank as undeliverable.

## Root Cause

The EC Payment Information update replicated to ECP infotype IT0009 (Bank Details) via the nightly batch. However, the replication job ran at 02:00 on 2026-01-04 — and the payroll calculation lock (payroll area `US-BIWEEKLY-01`) was applied at 22:00 on 2026-01-03, before the replication ran. The updated bank record was received by ECP after the payroll calculation was already frozen for the Jan 10 pay date.

This is a timing issue: EC→ECP bank detail replication must complete before the payroll lock date, not just before the pay date.

## Workaround

Payroll Ops issued a manual check for the affected payroll amount. The returned ACH funds will clear to Meridian's payroll account within 5 business days. Payroll Ops tracked the return and verified the manual check was received by the employee.

## Resolution

Bank details corrected in ECP (IT0009). Employee's next payroll run (Jan 24) will use the correct account. Payroll Ops updated the employee communication in `accessing-pay-statements.md` to note the payroll lock cutoff: bank changes must be submitted in EC by the **Wednesday before the pay date** to take effect in the current cycle.

## Related

- ECP infotype IT0009 (Bank Details)
- EC→ECP replication schedule: nightly batch 02:00 UTC
- Payroll lock schedule: `US-BIWEEKLY-01` locks at 22:00 two days before pay date
