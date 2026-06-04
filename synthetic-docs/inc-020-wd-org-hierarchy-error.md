# INC-0070901 — Workday Org Hierarchy Shows Circular Reporting Relationship

**system_affected**: Workday_HCM
**resolution_status**: resolved
**reported_date**: 2025-08-11
**resolved_date**: 2025-08-13
**ticket_type**: incident
**reported_by**: HRIS Team (proactive detection)

## Description

The Workday HRIS team identified a circular reporting relationship in the subsidiary org structure during a routine org audit. Employee A (WD-3310, VP Engineering) reports to Employee B (WD-3411, Director Engineering) in Workday, AND Employee B reports to Employee A. This creates a circular supervisory organization chain. Workday displays an error when attempting to navigate the org chart for either employee, and the EIB load that originally created the error generated a validation warning that was not caught at the time.

## Root Cause

The circular relationship was introduced during an EIB (Enterprise Interface Builder) bulk load in July to restructure the Engineering department. The EIB template row for Employee B accidentally referenced Employee A's Workday ID as Employee B's manager — and Employee A's row already referenced Employee B's legacy manager, but a subsequent manual update (outside the EIB) changed Employee A's manager to Employee B without catching the resulting loop.

Workday's EIB validation at load time checks for valid manager IDs but does not perform circular relationship detection at the time of load — only during subsequent org chart rendering.

## Workaround

Workday admin corrected the supervisory organization assignment for Employee B to the correct manager (WD-3100, SVP Engineering) via Workday Admin → Organization → Reassign Supervisory Organization.

## Resolution

Org structure corrected. Both employees' org chart views render correctly. HRIS added a post-EIB validation step: after any bulk org structure load, run the **Organization Hierarchy Audit** report (Workday standard report) before closing the change window.

## Related

- Workday EIB: Enterprise Interface Builder — used for bulk data loads
- Workday standard report: Organization Hierarchy Audit
- Circular supervisory org relationships block downstream business processes including time-off approvals and performance review routing
