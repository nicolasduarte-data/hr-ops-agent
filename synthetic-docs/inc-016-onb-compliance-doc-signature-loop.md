# INC-0070634 — Onboarding Compliance Doc E-Signature Loop

**system_affected**: SuccessFactors_ONB
**resolution_status**: in-progress
**reported_date**: 2026-01-14
**resolved_date**:
**ticket_type**: incident
**reported_by**: New hire (via HR Ops)

## Description

A new hire (ID: MRD-5288, start date: 2026-01-20) is unable to complete the electronic signature step for the Employee Handbook Acknowledgement in SF ONB 2.0. After clicking **Sign** in the document viewer, the e-signature confirmation screen loads but immediately redirects back to the document — creating an infinite loop. The document status stays "Pending Signature" indefinitely.

Confirmed on Chrome 131 (Windows) and Edge 131. Not yet tested on Safari.

## Root Cause (Preliminary)

The e-signature workflow in SF ONB 2.0 uses a redirect-based session token handoff between the document viewer iframe and the signature confirmation page. Preliminary investigation indicates a third-party cookie restriction change in Chrome 131 (Chromium's new Partitioned Cookies / CHIPS enforcement) is blocking the session token from being read by the confirmation page when it loads in a new context.

SAP Community thread (community.sap.com/t5/successfactors/onboarding-esignature-loop-chrome-131) reports the same pattern from other SuccessFactors customers. SAP support case INC-SAP-9102 raised.

## Workaround

Employees can complete the e-signature in Firefox (any current version) or Safari — the redirect token is handled correctly in those browsers. HR Ops is communicating this workaround to affected new hires.

HRIS will test with Chrome 131 in Incognito mode (third-party cookies less restricted) — preliminary result: Incognito mode resolves the loop. Communicating to new hires as a secondary option.

## Resolution

Pending SAP patch. SAP has acknowledged the issue and confirmed a hotfix is targeted for the next SF ONB maintenance release (estimated 2026-01-28). HRIS will validate in test tenant before applying to production.

## Related

- SAP Community thread: successfactors → onboarding-esignature-loop-chrome-131
- SAP support case: INC-SAP-9102
- Browser compatibility note applies to any SF ONB 2.0 e-signature workflow
