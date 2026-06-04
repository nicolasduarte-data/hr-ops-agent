# INC-0071612 — Concur Flagging Valid Meal Expense as Policy Violation

**system_affected**: SAP_Concur
**resolution_status**: resolved
**reported_date**: 2025-09-08
**resolved_date**: 2025-09-09
**ticket_type**: incident
**reported_by**: Finance / Accounts Payable

## Description

Multiple employees are reporting that valid business meal expenses are being flagged with a "Policy Violation — Meal Limit Exceeded" alert in Concur, even when the meal amount is under the published meal limit ($75 for dinner). Investigation shows 12 separate reports in September with this pattern. The flagged amounts range from $58 to $71 — all under the $75 dinner limit.

## Root Cause

Concur's expense policy configuration uses an audit rule that checks meal costs against a limit. The audit rule was last updated 18 months ago when the meal limits were lower ($60 for dinner). The Finance team approved a meal limit increase to $75 in Q1 2025, but the Concur audit rule was not updated at that time — only the policy document was updated. The system was still enforcing the old $60 limit.

## Workaround

Employees can add a justification note in the report comment field: "Expense within current approved meal policy limit ($75 dinner)." Finance/AP is approving these reports manually when accompanied by the justification note.

## Resolution

Concur admin updated the dinner meal audit rule limit from $60 to $75. Deployed same day (Concur policy rules take effect on next report submission). Finance confirmed no further false-positive policy alerts after the update.

Concur admin documented a change management process: any meal policy limit update must include a Concur audit rule update in the same change request — Finance policy owner and Concur admin are now joint approvers on meal limit changes.

## Related

- `submitting-expenses.md` — current meal limits ($75 dinner) are documented
- Concur audit rules: Finance/AP team should own and review quarterly
