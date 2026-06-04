"""Unit tests for tool functions — happy path + not-found path per tool.

Two fixture modes:
  use_real_docs (autouse)   — patches get_docs() with real synthetic docs AND
                               patches the retrieval layer to raise (fallback mode).
                               Keeps tests fast (no model load) while testing the
                               full tool contract with real doc content.

  with_mock_retriever       — injects a pre-configured mock HybridRetriever for
                               testing the retrieval-backed code path without a model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.agent.doc_loader import load_documents
from src.agent.tools import (
    dispatch_tool,
    get_escalation_path,
    get_it_scope,
    lookup_known_issues,
    search_process_docs,
)
from src.retrieval.chunker import Chunk
from src.retrieval.retriever import SearchResult

DOCS_DIR = Path(__file__).parent.parent / "synthetic-docs"


def _make_mock_result(
    content: str = "Workaround: clear cookies.",
    filename: str = "inc-007.md",
    section_header: str = "Workaround",
    doc_title: str = "Test Issue",
    system_affected: str = "SuccessFactors_EC",
    resolution_status: str = "resolved",
    doc_type: str = "known_issue",
) -> SearchResult:
    chunk = Chunk(
        chunk_id=f"{filename}::0",
        doc_title=doc_title,
        doc_type=doc_type,  # type: ignore[arg-type]
        filename=filename,
        last_updated_date="2026-01-01",
        section_header=section_header,
        content=content,
        system_affected=system_affected,
        resolution_status=resolution_status,
    )
    return SearchResult(chunk=chunk, score=0.9, rank=1)


@pytest.fixture(autouse=True)
def use_real_docs() -> Any:
    """Patch get_docs() with real docs AND force retrieval layer to fall back.

    Fallback is forced by patching get_retriever to raise ImportError,
    which triggers the except-branch in search_process_docs / lookup_known_issues.
    This keeps tests model-free and fast.
    """
    import src.agent.doc_loader as loader_mod
    import src.agent.tools as tools_mod

    real_docs = load_documents(DOCS_DIR)
    with (
        patch.object(loader_mod, "_DOCS", real_docs),
        patch.object(tools_mod, "get_docs", return_value=real_docs),
        patch("src.retrieval.retriever.get_retriever", side_effect=ImportError("retrieval unavailable")),
    ):
        yield


@pytest.fixture()
def mock_retriever() -> MagicMock:
    """A pre-wired mock HybridRetriever for testing the retrieval code path."""
    r = MagicMock()
    r.search_process_docs.return_value = [
        _make_mock_result(
            content="Time off requests are submitted through Workday.",
            filename="requesting-time-off.md",
            section_header="Overview",
            doc_title="Requesting Time Off",
            system_affected="",
            resolution_status="",
            doc_type="process",
        )
    ]
    r.lookup_known_issues.return_value = [
        _make_mock_result(
            content="PA30 is locked by another user. Workaround: ask them to release the lock.",
            filename="inc-021-pa30-lock.md",
            section_header="Workaround",
            doc_title="INC-021 — PA30 Lock",
            system_affected="SAP_Concur",
            resolution_status="resolved",
            doc_type="known_issue",
        )
    ]
    return r


# ---------------------------------------------------------------------------
# search_process_docs
# ---------------------------------------------------------------------------


class TestSearchProcessDocs:
    def test_happy_path_pto(self) -> None:
        result = search_process_docs("how to request PTO in Workday")
        assert result["found"] is True
        assert result["source"] in ("hr-processes.md", "onboarding-checklist.md")
        assert len(result["excerpt"]) > 50

    def test_happy_path_onboarding(self) -> None:
        result = search_process_docs("new hire onboarding checklist day 1")
        assert result["found"] is True
        assert result["excerpt"]

    def test_not_found(self) -> None:
        result = search_process_docs("xyzzy quantum blockchain synergy")
        assert result["found"] is False
        assert result["excerpt"] == ""

    def test_expense_submission(self) -> None:
        result = search_process_docs("submit expense report Concur")
        assert result["found"] is True


# ---------------------------------------------------------------------------
# lookup_known_issues
# ---------------------------------------------------------------------------


class TestLookupKnownIssues:
    def test_happy_path_sso_loop(self) -> None:
        result = lookup_known_issues("Workday SSO login loop after password reset")
        assert result["found"] is True
        assert result["source"] == "known-issues.md"
        assert "workaround" in result["excerpt"].lower() or "cookie" in result["excerpt"].lower()

    def test_happy_path_pa30(self) -> None:
        result = lookup_known_issues("PA30 locked by another user")
        assert result["found"] is True
        assert "PA30" in result["excerpt"] or "lock" in result["excerpt"].lower()

    def test_not_found_returns_message(self) -> None:
        result = lookup_known_issues("xyzzy unfindable issue description")
        assert result["found"] is False
        assert "message" in result
        assert "ServiceNow" in result["message"]


# ---------------------------------------------------------------------------
# get_it_scope
# ---------------------------------------------------------------------------


class TestGetItScope:
    def test_happy_path_okta(self) -> None:
        result = get_it_scope("Okta SSO identity management")
        assert result["found"] is True
        assert result["source"] == "it-scope.md"

    def test_happy_path_integration(self) -> None:
        result = get_it_scope("CPI iFlow SAP integration")
        assert result["found"] is True

    def test_happy_path_payroll(self) -> None:
        result = get_it_scope("payroll ECP processing")
        assert result["found"] is True

    def test_not_found_returns_message(self) -> None:
        result = get_it_scope("nonexistent-system-xyzzy-123")
        assert result["found"] is False
        assert "message" in result
        assert "it-scope.md" in result["message"] or "hris-support" in result["message"]


# ---------------------------------------------------------------------------
# get_escalation_path
# ---------------------------------------------------------------------------


class TestGetEscalationPath:
    def test_happy_path_iam_p1(self) -> None:
        result = get_escalation_path("IAM", "P1")
        assert result["found"] is True
        assert result["source"] == "escalation-matrix.md"

    def test_happy_path_integration_p2(self) -> None:
        result = get_escalation_path("Integration", "P2")
        assert result["found"] is True

    def test_happy_path_payroll(self) -> None:
        result = get_escalation_path("Payroll", "P3")
        assert result["found"] is True

    def test_not_found_returns_message(self) -> None:
        result = get_escalation_path("xyzzy-team", "P99")
        assert result["found"] is False
        assert "message" in result
        assert "ServiceNow" in result["message"]


# ---------------------------------------------------------------------------
# dispatch_tool
# ---------------------------------------------------------------------------


class TestDispatchTool:
    def test_known_tool_returns_json(self) -> None:
        raw = dispatch_tool("search_process_docs", {"query": "time off"})
        parsed = json.loads(raw)
        assert "found" in parsed

    def test_unknown_tool_returns_error_json(self) -> None:
        raw = dispatch_tool("nonexistent_tool", {})
        parsed = json.loads(raw)
        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

    def test_missing_argument_raises(self) -> None:
        """dispatch_tool re-raises tool exceptions so orchestrator's is_error fires."""
        with pytest.raises(TypeError):
            dispatch_tool("search_process_docs", {})


# ---------------------------------------------------------------------------
# Retrieval-backed tool path (mock retriever, no model required)
# ---------------------------------------------------------------------------


class TestSearchProcessDocsWithRetriever:
    """Tests for the retrieval-backed code path in search_process_docs."""

    def test_returns_retriever_result(self, mock_retriever: MagicMock) -> None:
        with patch("src.retrieval.retriever.get_retriever", return_value=mock_retriever):
            result = search_process_docs("how to request time off")
        assert result["found"] is True
        assert "Workday" in result["excerpt"]
        assert result["source"] == "requesting-time-off.md"
        assert result["section"] == "Overview"
        assert result["doc_title"] == "Requesting Time Off"

    def test_returns_not_found_when_retriever_empty(self, mock_retriever: MagicMock) -> None:
        mock_retriever.search_process_docs.return_value = []
        with patch("src.retrieval.retriever.get_retriever", return_value=mock_retriever):
            result = search_process_docs("obscure query")
        assert result["found"] is False

    def test_fallback_on_retriever_exception(self) -> None:
        """If retriever raises, tool falls back to naive keyword search."""
        with patch("src.retrieval.retriever.get_retriever", side_effect=RuntimeError("model crash")):
            result = search_process_docs("time off")
        # Fallback to naive — real docs are patched in via use_real_docs fixture
        assert "found" in result


class TestLookupKnownIssuesWithRetriever:
    """Tests for the retrieval-backed code path in lookup_known_issues."""

    def test_returns_retriever_result_with_metadata(self, mock_retriever: MagicMock) -> None:
        with patch("src.retrieval.retriever.get_retriever", return_value=mock_retriever):
            result = lookup_known_issues("PA30 locked by another user")
        assert result["found"] is True
        assert "PA30" in result["excerpt"]
        assert result["source"] == "inc-021-pa30-lock.md"
        assert result["system_affected"] == "SAP_Concur"
        assert result["resolution_status"] == "resolved"

    def test_not_found_includes_servicenow_message(self, mock_retriever: MagicMock) -> None:
        mock_retriever.lookup_known_issues.return_value = []
        with patch("src.retrieval.retriever.get_retriever", return_value=mock_retriever):
            result = lookup_known_issues("unfindable error")
        assert result["found"] is False
        assert "ServiceNow" in result["message"]

    def test_result_without_system_affected_excluded_from_response(
        self, mock_retriever: MagicMock
    ) -> None:
        """system_affected / resolution_status should be omitted if empty string."""
        from src.retrieval.chunker import Chunk
        from src.retrieval.retriever import SearchResult

        chunk = Chunk(
            chunk_id="known-issues.md::0",
            doc_title="Known Issues",
            doc_type="known_issue",
            filename="known-issues.md",
            last_updated_date="2026-01-01",
            section_header="",
            content="Some workaround content.",
            system_affected="",     # empty — should not appear in result
            resolution_status="",   # empty — should not appear in result
        )
        mock_retriever.lookup_known_issues.return_value = [
            SearchResult(chunk=chunk, score=0.8, rank=1)
        ]
        with patch("src.retrieval.retriever.get_retriever", return_value=mock_retriever):
            result = lookup_known_issues("some issue")
        assert result["found"] is True
        assert "system_affected" not in result
        assert "resolution_status" not in result
