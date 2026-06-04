"""Tests for src/retrieval/chunker.py.

No model dependencies — pure Python, runs offline.
"""

from __future__ import annotations

from src.retrieval.chunker import (
    _parse_frontmatter_field,
    _parse_incident_date,
    _parse_last_updated,
    _split_on_h2,
    _split_oversized,
    chunk_document,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

POLICY_DOC = """\
# Requesting Time Off — Meridian HR Self-Service Guide

**System**: Workday HCM
**Applies to**: All regular employees
**Last updated**: 2026-01-15
**Owner**: HR Operations

---

## Overview

All time-off requests at Meridian are submitted through Workday.

## PTO and Sick Leave — Standard Requests

1. Log into Workday.
2. Click Time Off.
3. Select PTO type.

## Leave of Absence

For extended leave, contact HR Operations directly.
"""

INCIDENT_DOC = """\
# INC-0070034 — EC Position Not Syncing After Promotion

**system_affected**: SuccessFactors_EC
**resolution_status**: resolved
**reported_date**: 2025-11-04
**resolved_date**: 2025-11-06
**ticket_type**: incident
**reported_by**: Maria Santos (HR Operations)

## Description

After completing a promotion workflow the position title is not replicating.

## Root Cause

CPI delta watches Employment object, not Position object.

## Workaround

Manually trigger full-sync via CPI monitoring console.

## Resolution

Updated CPI iFlow to watch Position object. Deployed 2025-11-06.
"""


# ---------------------------------------------------------------------------
# _split_on_h2
# ---------------------------------------------------------------------------

class TestSplitOnH2:
    def test_splits_on_h2_headers(self) -> None:
        sections = _split_on_h2(POLICY_DOC)
        headers = [h for h, _ in sections]
        assert "## Overview" in headers
        assert "## PTO and Sick Leave — Standard Requests" in headers
        assert "## Leave of Absence" in headers

    def test_preamble_captured_with_empty_header(self) -> None:
        sections = _split_on_h2(POLICY_DOC)
        preamble_header, preamble_body = sections[0]
        assert preamble_header == ""
        assert "Requesting Time Off" in preamble_body

    def test_h3_not_treated_as_split_point(self) -> None:
        content = "## Overview\n\n### Sub-section\n\nContent.\n"
        sections = _split_on_h2(content)
        assert len(sections) == 1  # only one ## section, h3 stays inside

    def test_empty_content_returns_empty_list(self) -> None:
        # _split_on_h2 returns [] for empty input.
        # _chunk_policy_doc's fallback handles the empty-doc case by producing
        # one atomic chunk — this function just reports what sections exist.
        sections = _split_on_h2("")
        assert sections == []


# ---------------------------------------------------------------------------
# _split_oversized
# ---------------------------------------------------------------------------

class TestSplitOversized:
    def test_short_text_returned_as_single_chunk(self) -> None:
        text = "Short content."
        result = _split_oversized(text)
        assert result == [text]

    def test_oversized_text_splits_on_blank_lines(self) -> None:
        paragraph = "word " * 200  # ~1000 chars
        text = f"{paragraph}\n\n{paragraph}\n\n{paragraph}\n\n{paragraph}"
        result = _split_oversized(text)
        assert len(result) > 1
        # Each piece should be within the limit (with some tolerance for paragraph grouping)
        for piece in result:
            assert len(piece) < 5000  # reasonable upper bound

    def test_content_not_lost_during_split(self) -> None:
        para = "unique_token_xyz " * 100
        text = f"{para}\n\n{para}\n\n{para}\n\n{para}"
        result = _split_oversized(text)
        combined = " ".join(result)
        # Count of the unique token should be preserved
        original_count = text.count("unique_token_xyz")
        combined_count = combined.count("unique_token_xyz")
        assert combined_count == original_count


# ---------------------------------------------------------------------------
# Metadata parsers
# ---------------------------------------------------------------------------

class TestParseLastUpdated:
    def test_parses_bold_format(self) -> None:
        content = "# Title\n\n**Last updated**: 2026-01-15\n"
        assert _parse_last_updated(content) == "2026-01-15"

    def test_case_insensitive(self) -> None:
        content = "**Last Updated**: 2025-12-01\n"
        assert _parse_last_updated(content) == "2025-12-01"

    def test_returns_unknown_if_absent(self) -> None:
        assert _parse_last_updated("No date here.") == "unknown"

    def test_strips_trailing_pipe(self) -> None:
        content = "**Last updated**: 2026-01-15 | extra\n"
        assert _parse_last_updated(content) == "2026-01-15"


class TestParseFrontmatterField:
    def test_parses_system_affected(self) -> None:
        assert _parse_frontmatter_field(INCIDENT_DOC, "system_affected") == "SuccessFactors_EC"

    def test_parses_resolution_status(self) -> None:
        assert _parse_frontmatter_field(INCIDENT_DOC, "resolution_status") == "resolved"

    def test_returns_empty_if_absent(self) -> None:
        assert _parse_frontmatter_field("No field here.", "system_affected") == ""

    def test_only_searches_first_20_lines(self) -> None:
        # Field present at line 25 should NOT be found
        header = "# Title\n" * 22
        content = header + "**system_affected**: SuccessFactors_EC\n"
        assert _parse_frontmatter_field(content, "system_affected") == ""


class TestParseIncidentDate:
    def test_prefers_resolved_date(self) -> None:
        assert _parse_incident_date(INCIDENT_DOC) == "2025-11-06"

    def test_falls_back_to_reported_date_if_unresolved(self) -> None:
        content = INCIDENT_DOC.replace("**resolved_date**: 2025-11-06\n", "")
        assert _parse_incident_date(content) == "2025-11-04"

    def test_returns_unknown_if_no_dates(self) -> None:
        assert _parse_incident_date("No dates here.") == "unknown"


# ---------------------------------------------------------------------------
# chunk_document: policy docs
# ---------------------------------------------------------------------------

class TestChunkDocumentPolicyDoc:
    def test_produces_multiple_chunks(self) -> None:
        chunks = chunk_document(POLICY_DOC, "requesting-time-off.md")
        assert len(chunks) >= 2  # preamble + at least Overview

    def test_chunk_metadata(self) -> None:
        chunks = chunk_document(POLICY_DOC, "requesting-time-off.md")
        for c in chunks:
            assert c.filename == "requesting-time-off.md"
            assert c.doc_type == "process"
            assert c.doc_title  # non-empty
            assert c.last_updated_date == "2026-01-15"
            assert c.chunk_id.startswith("requesting-time-off.md::")

    def test_section_headers_captured(self) -> None:
        chunks = chunk_document(POLICY_DOC, "requesting-time-off.md")
        headers = {c.section_header for c in chunks}
        assert "Overview" in headers
        assert "PTO and Sick Leave — Standard Requests" in headers

    def test_no_empty_chunks(self) -> None:
        chunks = chunk_document(POLICY_DOC, "requesting-time-off.md")
        for c in chunks:
            assert c.content.strip()

    def test_known_issues_md_gets_known_issue_type(self) -> None:
        chunks = chunk_document("# Known Issues\n\n## ISSUE-001\n\nContent.", "known-issues.md")
        for c in chunks:
            assert c.doc_type == "known_issue"

    def test_onboarding_checklist_gets_onboarding_type(self) -> None:
        chunks = chunk_document("# Onboarding Checklist\n\n## Step 1\n\nContent.", "onboarding-checklist.md")
        for c in chunks:
            assert c.doc_type == "onboarding"

    def test_unknown_filename_defaults_to_process(self) -> None:
        chunks = chunk_document("# Some Doc\n\n## Section\n\nContent.", "some-new-policy.md")
        for c in chunks:
            assert c.doc_type == "process"


# ---------------------------------------------------------------------------
# chunk_document: ITSM incident records
# ---------------------------------------------------------------------------

class TestChunkDocumentIncident:
    def test_produces_single_atomic_chunk(self) -> None:
        chunks = chunk_document(INCIDENT_DOC, "inc-007-ec-position-not-syncing.md")
        assert len(chunks) == 1

    def test_incident_metadata(self) -> None:
        chunks = chunk_document(INCIDENT_DOC, "inc-007-ec-position-not-syncing.md")
        c = chunks[0]
        assert c.doc_type == "known_issue"
        assert c.system_affected == "SuccessFactors_EC"
        assert c.resolution_status == "resolved"
        assert c.last_updated_date == "2025-11-06"
        assert c.filename == "inc-007-ec-position-not-syncing.md"
        assert c.chunk_id == "inc-007-ec-position-not-syncing.md::0"

    def test_incident_content_complete(self) -> None:
        chunks = chunk_document(INCIDENT_DOC, "inc-007-ec-position-not-syncing.md")
        content = chunks[0].content
        # All four sections should be present in the atomic chunk
        assert "Description" in content
        assert "Root Cause" in content
        assert "Workaround" in content
        assert "Resolution" in content

    def test_incident_section_header_is_empty(self) -> None:
        chunks = chunk_document(INCIDENT_DOC, "inc-007-ec-position-not-syncing.md")
        assert chunks[0].section_header == ""

    def test_ticket_system_affected_empty_for_policy(self) -> None:
        chunks = chunk_document(POLICY_DOC, "requesting-time-off.md")
        for c in chunks:
            assert c.system_affected == ""
            assert c.resolution_status == ""
