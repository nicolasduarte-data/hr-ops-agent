# INC-0071002 — EIB Load Failed — Date Format Validation Error

**system_affected**: Workday_Integration
**resolution_status**: resolved
**reported_date**: 2025-12-03
**resolved_date**: 2025-12-04
**ticket_type**: incident
**reported_by**: Integration Team

## Description

An Enterprise Interface Builder (EIB) load for bulk compensation updates (annual merit cycle) failed with validation error: `DATE_FORMAT_INVALID: Field 'Effective Date' — expected YYYY-MM-DD, received MM/DD/YYYY (row 47 and 183 of 412 total rows)`. The entire EIB batch was rejected — no records updated.

## Root Cause

The EIB template for compensation changes uses the Workday standard date format `YYYY-MM-DD`. The HR analyst who prepared the file used Excel's default date display format (`MM/DD/YYYY` — US locale). Excel stored the underlying data correctly but when saved as CSV, exported the date values in the display format, not the ISO format required by the EIB schema.

This is a common EIB authoring error. Workday validates date format at load time and rejects the entire batch on any format violation (EIB strict mode — configured by Meridian admin).

## Workaround

Integration team corrected the two malformed date values in the CSV and reloaded the EIB. Batch processed successfully on the second attempt — all 412 rows loaded.

## Resolution

Immediate: corrected CSV reloaded. No data integrity impact since original load was fully rejected (no partial applies in strict mode).

Long-term: Integration team updated the EIB template (Excel) to force `YYYY-MM-DD` format on date columns via cell format string `YYYY-MM-DD`. Added a pre-load validation step in the Compensation Change SOP: open CSV in a text editor to verify date column formatting before submitting.

## Related

- Workday EIB documentation: Date format requirements — ISO 8601 (YYYY-MM-DD) required for all date fields
- Related: Known-issues.md ISSUE-004 (EIB supervisory org validation error — different error type, same tool)
