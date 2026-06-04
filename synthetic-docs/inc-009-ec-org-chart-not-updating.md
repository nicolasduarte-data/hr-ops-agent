# INC-0070154 — EC Org Chart Not Reflecting Manager Change

**system_affected**: SuccessFactors_EC
**resolution_status**: in-progress
**reported_date**: 2025-12-02
**resolved_date**:
**ticket_type**: incident
**reported_by**: Dana Reyes (HR Operations)

## Description

Following a department restructure, 14 employees were moved to a new manager via a mass EC data change (transaction PA40-equivalent in SF EC — Job Information change). The changes are correctly reflected in individual employee records (Job Information → Reports To field shows the new manager), but the SF EC org chart widget still displays the old reporting structure for all 14 affected employees. The org chart has not updated after 72 hours.

## Root Cause (Preliminary)

EC org chart data is cached separately from the Job Information record. The cache refresh for the org chart visualization runs on a nightly batch job. Preliminary investigation shows the batch job for org chart regeneration failed on the night of 2025-12-02 due to a timeout — the org structure query exceeded the 30-second job timeout after the mass change created a large delta payload.

HRIS is working with SAP support to manually trigger an org chart cache rebuild.

## Workaround

Employees can still view accurate reporting relationships by navigating directly to a colleague's **Profile → Employment Information → Job Information** (shows correct manager), rather than using the visual org chart widget.

For managers needing the accurate structure for planning purposes, HR Ops can export the org hierarchy from EC → Reporting → Ad Hoc Reports as a CSV.

## Resolution

In progress. SAP support ticket INC-SAP-8844 raised. Manual cache rebuild attempted 2025-12-04 — pending validation. Expected resolution: 2025-12-06.

## Related

- Affects only the org chart display; all individual records are accurate
- No downstream replication impact (CPI integration reads Job Information, not the org chart cache)
