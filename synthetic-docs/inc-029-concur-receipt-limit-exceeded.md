# INC-0071554 — Concur Expense Report Blocked — Receipt File Size Limit Exceeded

**system_affected**: SAP_Concur
**resolution_status**: resolved
**reported_date**: 2025-10-03
**resolved_date**: 2025-10-03
**ticket_type**: incident
**reported_by**: Employee self-reported

## Description

An employee is unable to submit an expense report in Concur. When clicking "Submit," the system returns error: "One or more receipts exceed the maximum file size limit (5 MB per receipt)." The employee photographed hotel receipts using the Concur mobile app and several photos are large (8–12 MB) from a high-resolution camera.

## Root Cause

Concur's attachment upload enforces a 5 MB per-file limit for receipt images. The Concur mobile app captures photos using the device camera settings — on modern smartphones, camera settings default to full resolution (12+ MP), producing images well above the 5 MB limit. Concur does not automatically compress images on mobile upload.

This is a known Concur limitation documented in SAP Concur Help: "Receipt Image Requirements."

## Workaround

The employee can reduce receipt image file size by:
1. **On iPhone**: before capturing in Concur app, go to iPhone Settings → Camera → Formats → select "Most Compatible" and reduce resolution if available.
2. **On Android**: use the Concur app's built-in camera (which automatically captures at a lower resolution than the native camera) rather than uploading from the photo gallery.
3. **Desktop alternative**: scan receipts and save as compressed PDF (max 5 MB); upload via Concur desktop.
4. **Image compression tool**: use any online compression tool to reduce JPEG/PNG to under 5 MB before upload.

## Resolution

Workaround applied — employee compressed images and submitted successfully. Finance/AP added a note to the Concur user guide in ServiceNow KB: "Receipt photos must be under 5 MB; use the Concur in-app camera for automatic compression."

## Related

- SAP Concur Help: Receipt Image Requirements — `concurtraining.com/customers/merck/TE/client_tools/`
- Concur mobile app best practice: always use the Concur in-app camera rather than uploading from gallery
