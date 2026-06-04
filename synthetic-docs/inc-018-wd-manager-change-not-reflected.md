# INC-0070762 — Workday Not Reflecting Manager Change After EC Update

**system_affected**: Workday_HCM
**resolution_status**: resolved
**reported_date**: 2025-09-30
**resolved_date**: 2025-10-02
**ticket_type**: incident
**reported_by**: HR Operations

## Description

Following a manager reassignment processed in SF EC on 2025-09-29 (effective 2025-09-29), the employee's manager in the Workday tenant (subsidiary) still shows the old manager 48 hours later. The EC record is correct. The employee's time-off requests are being routed to the old manager for approval.

## Root Cause

The CPI integration for EC→Workday employee sync uses a **delta replication** model — it only transmits records where a monitored field has changed since the last run. The manager field in EC is stored on the `Job Information` object, and specifically the `Functional Manager` relationship. The CPI iFlow monitors changes to `Reporting Manager` but not `Functional Manager`. The reassignment was entered as a Functional Manager change (not a Reporting Manager change), so the CPI delta query did not include the affected employee in its payload.

This is a known gap in the CPI iFlow configuration.

## Workaround

HRIS used the CPI integration console to trigger a full-sync for the affected employee (same procedure as INC-0070034). Workday reflected the correct manager within 2 hours of the manual trigger.

## Resolution

Immediate: manual sync applied. Long-term: HRIS updated the CPI delta query to monitor both `Reporting Manager` and `Functional Manager` field changes on the Job Information object. Deployed 2025-10-02. Validated against subsequent manager change transactions.

## Related

- INC-0070034 (EC position not syncing — same CPI delta configuration gap)
- CPI iFlow: `EC-to-Workday-Employee-Delta`
