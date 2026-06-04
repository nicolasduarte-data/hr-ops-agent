# INC-0071488 — Concur Delegate Cannot Submit Expense Report on Behalf of Traveler

**system_affected**: SAP_Concur
**resolution_status**: resolved
**reported_date**: 2025-11-11
**resolved_date**: 2025-11-12
**ticket_type**: incident
**reported_by**: Finance / AP Team

## Description

An executive assistant (EA) who is set up as a delegate for a VP (submitter role) attempted to submit an expense report on the VP's behalf but received error: "Delegate does not have Submit access for this user." The EA has been a delegate for this VP for 8 months without issue. A recent change appears to have affected the delegation configuration.

## Root Cause

Concur delegation permissions are controlled by the submitter (the VP), not the delegate (the EA). The submitter must grant "Can Submit Reports" permission to the delegate in **Concur → Profile → Expense Delegates**. Investigation showed the VP's delegate settings were reset to default (Can Prepare, Can View — but not Can Submit) during a bulk Concur user profile synchronization that ran on 2025-11-08. The sync was part of a user directory update and inadvertently overwrote custom delegation settings for 7 users.

## Workaround

EA asked the VP to re-grant the "Can Submit Reports" permission:
- VP logged into Concur → Profile Settings → Expense Delegates → locate EA → check "Can Submit Reports."

Permission restored. EA confirmed submit access within 5 minutes.

## Resolution

Immediate fix applied for all 7 affected users (Finance team identified the full list from the sync log). Long-term: the user directory sync process was updated to preserve existing delegation permissions — the sync now writes only to fields outside the delegation scope. Concur admin documented the sync exclusion list.

## Related

- Concur Profile Settings → Expense Delegates — submitter must grant Can Submit permission
- Delegation configuration is submitter-owned and should be preserved during any bulk sync
