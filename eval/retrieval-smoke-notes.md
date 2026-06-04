# Retrieval Smoke Notes — Naive Lookup Failures

Demonstrates that naive keyword lookup fails on queries that hybrid BM25+dense retrieval
should catch. These are the demo cases for hybrid retrieval — each is a real query
against the M2 corpus that keyword matching misses or returns wrong results.

---

## Miss 1 — Exact T-code query: "PA30 locked"

**Query**: "transaction PA30 is locked by another user, what do I do?"

**Naive lookup behavior**: The naive tool (`lookup_known_issues`) uses simple substring matching
on the query text. The string "PA30" does not appear in the general descriptions or workarounds
of the five M1 docs — it's only present in `known-issues.md` and in the new M2 ticket record
`inc-007-ec-position-not-syncing.md`. A dense embedding query for "transaction PA30 locked"
may retrieve general "process locked" or "user access" documents based on semantic similarity
rather than the specific T-code match.

**Expected retrieval**: `known-issues.md` (ISSUE-006: Transaction PA30 locked by another user)
and/or `inc-007-ec-position-not-syncing.md`.

**Why BM25 catches it**: "PA30" is a rare, domain-specific token. BM25 assigns it a very high
inverse document frequency (IDF) weight — it appears in only 2 of 42 documents. A BM25-primary
or hybrid query returns the exact match immediately.

**Naive miss mechanism**: Dense embedding encodes "PA30" as part of a broader "SAP transaction"
concept — it may retrieve documents about SAP access or HR processes generically rather than
the specific PA30 workaround.

---

## Miss 2 — Module acronym: "EIB supervisory org"

**Query**: "EIB load failed with supervisory org validation error, how do I fix it?"

**Naive lookup behavior**: Naive substring matching on "EIB" or "supervisory org" may not
match if the query phrasing differs from the document phrasing. Dense embedding of "EIB load
failed" encodes the semantic concept of "integration load failure," which could match many
integration-related documents (inc-021, inc-022, inc-023) based on general theme rather than
the specific EIB→supervisory org error pattern.

**Expected retrieval**: `known-issues.md` (ISSUE-004: EIB load failed — supervisory org
validation) and `inc-021-wd-eib-date-format-error.md`.

**Why BM25 catches it**: "EIB" is a high-IDF token (appears in 4 of 42 documents).
"supervisory org" also has elevated IDF. BM25 hybrid returns the correct documents ranked
first based on exact token overlap.

**Naive miss mechanism**: Dense embedding distances between "EIB supervisory org validation"
and "EIB date format error" are similar — both are "EIB failures." Dense-only retrieval may
return INC-021 (date format, lower relevance) alongside or instead of ISSUE-004 (supervisory
org, higher relevance for this query).

---

## Miss 3 — ITSM code: "RITM not routing"

**Query**: "My RITM was created but went to the wrong team, who do I contact?"

**Naive lookup behavior**: The query contains "RITM" — a ServiceNow-specific term. Naive
lookup may match broadly on "wrong team" (which appears in multiple docs) rather than the
ITSM-specific routing behavior. Dense embedding of "RITM routing wrong team" may match on
"team assignment" semantically across HR, IT, and ServiceNow documents without discriminating
for ServiceNow ITSM-specific context.

**Expected retrieval**: `inc-024-sn-ritm-routing-wrong-team.md` (exact match on the scenario
described) and `escalation-matrix.md` (for escalation guidance).

**Why BM25 catches it**: "RITM" is an extremely high-IDF token — it appears in only 3 of 42
documents and with high frequency in ServiceNow-specific records. BM25 immediately surfaces
the relevant ITSM documents.

**Naive miss mechanism**: "RITM not routing" is semantically similar to "request not processed"
or "approval not received" — dense embedding may return INC-026 (approval email not sent) or
INC-025 (HRSD case not created) as top results, neither of which answers the routing question.

---

## Summary

| Query | Expected doc | Naive miss type | BM25 token |
|---|---|---|---|
| "PA30 locked" | known-issues.md ISSUE-006 | Dense retrieves generic "access locked" docs | PA30 (high IDF) |
| "EIB supervisory org validation" | known-issues.md ISSUE-004 | Dense conflates different EIB error types | EIB + supervisory org |
| "RITM wrong team" | inc-024-sn-ritm-routing-wrong-team.md | Dense retrieves other "request not working" docs | RITM (high IDF) |

These three cases motivate the hybrid+RRF retrieval design: BM25 enforces exact-match
recall on domain-specific tokens; dense handles semantic paraphrase; RRF fuses both.
