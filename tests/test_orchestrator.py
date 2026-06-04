"""Integration tests for the orchestrator loop.

Uses a mocked Anthropic client to test routing logic without live API calls.
Tests: multi-tool query, MAX_TURNS guard, is_error path, end_turn extraction,
empty tool_results guard, empty _extract_text fallback.

The retrieval layer is patched to raise (forcing naive fallback in tools) so
these tests remain model-free and don't trigger BGE-M3/bge-small downloads.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.agent.orchestrator import run_agent


@pytest.fixture(autouse=True)
def _no_retrieval() -> Any:
    """Patch the retriever so tools fall back to naive keyword search.

    Without this, dispatch_tool → lookup_known_issues → get_retriever()
    would attempt to download and load the embedding model.
    """
    with patch(
        "src.retrieval.retriever.get_retriever",
        side_effect=ImportError("retrieval layer disabled in orchestrator tests"),
    ):
        yield


def _make_tool_use_block(name: str, tool_id: str, input_: dict[str, Any]) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.id = tool_id
    block.input = input_
    block.model_dump.return_value = {
        "type": "tool_use",
        "name": name,
        "id": tool_id,
        "input": input_,
    }
    return block


def _make_text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    block.model_dump.return_value = {"type": "text", "text": text}
    return block


def _make_response(stop_reason: str, blocks: list[MagicMock]) -> MagicMock:
    resp = MagicMock()
    resp.stop_reason = stop_reason
    resp.content = blocks
    return resp


class TestOrchestratorLoop:
    def test_single_turn_end_turn(self) -> None:
        """Simple query that resolves in one turn with no tools."""
        final_text = "Here is the answer."
        responses = [_make_response("end_turn", [_make_text_block(final_text)])]
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = responses

        with patch("src.agent.orchestrator.anthropic.Anthropic", return_value=mock_client):
            result = run_agent("How do I submit a PTO request?")

        assert result["answer"] == final_text
        assert result["tools_called"] == []
        assert result["turns"] == 1

    def test_multi_tool_query(self) -> None:
        """Query that triggers two tools, then end_turn after results."""
        tool_turn_blocks = [
            _make_tool_use_block(
                "lookup_known_issues", "tid-1", {"description": "Workday SSO loop"}
            ),
            _make_tool_use_block(
                "get_escalation_path", "tid-2", {"team": "IAM", "priority": "P1"}
            ),
        ]
        final_text = "Here is a synthesized answer from two tools."
        responses = [
            _make_response("tool_use", tool_turn_blocks),
            _make_response("end_turn", [_make_text_block(final_text)]),
        ]
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = responses

        with patch("src.agent.orchestrator.anthropic.Anthropic", return_value=mock_client):
            result = run_agent("My Workday login is looping. Who do I call for P1?")

        assert result["answer"] == final_text
        assert "lookup_known_issues" in result["tools_called"]
        assert "get_escalation_path" in result["tools_called"]
        assert result["turns"] == 2

    def test_max_turns_guard(self) -> None:
        """Agent that keeps calling tools hits MAX_TURNS and returns a message."""
        tool_block = _make_tool_use_block(
            "search_process_docs", "tid-loop", {"query": "anything"}
        )
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_response(
            "tool_use", [tool_block]
        )

        with (
            patch("src.agent.orchestrator.anthropic.Anthropic", return_value=mock_client),
            patch("src.agent.orchestrator.MAX_TURNS", 3),
        ):
            result = run_agent("Loop forever")

        assert "Maximum turn limit" in result["answer"]
        assert result["turns"] == 3

    def test_is_error_on_tool_exception(self) -> None:
        """When dispatch_tool raises, orchestrator sends is_error and continues."""
        tool_block = _make_tool_use_block(
            "lookup_known_issues", "tid-err", {"description": "trigger error"}
        )
        final_text = "I could not find the issue but here is general guidance."
        responses = [
            _make_response("tool_use", [tool_block]),
            _make_response("end_turn", [_make_text_block(final_text)]),
        ]
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = responses

        with (
            patch("src.agent.orchestrator.anthropic.Anthropic", return_value=mock_client),
            patch(
                "src.agent.orchestrator.dispatch_tool",
                side_effect=RuntimeError("simulated tool failure"),
            ),
        ):
            result = run_agent("Trigger an error")

        assert result["answer"] == final_text
        # Verify is_error was set in the batched tool_result
        call_args = mock_client.messages.create.call_args_list
        second_call_messages = call_args[1][1]["messages"]
        error_msg = second_call_messages[2]
        assert error_msg["role"] == "user"
        tool_result = error_msg["content"][0]
        assert tool_result.get("is_error") is True

    def test_unexpected_stop_reason(self) -> None:
        """Unexpected stop_reason returns an appropriate message."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_response(
            "pause_turn", []
        )

        with patch("src.agent.orchestrator.anthropic.Anthropic", return_value=mock_client):
            result = run_agent("test")

        assert "Unexpected stop reason" in result["answer"]

    def test_tool_use_with_no_tool_blocks_returns_error(self) -> None:
        """stop_reason=tool_use but no tool_use blocks — guard returns error, not crash."""
        text_only_block = _make_text_block("some text with no tool call")
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_response(
            "tool_use", [text_only_block]
        )

        with patch("src.agent.orchestrator.anthropic.Anthropic", return_value=mock_client):
            result = run_agent("test")

        assert "unexpected error" in result["answer"].lower()
        assert result["turns"] == 1

    def test_end_turn_no_text_block_returns_fallback(self) -> None:
        """end_turn with no text blocks returns a fallback message, not empty string."""
        tool_block_only = _make_tool_use_block(
            "search_process_docs", "tid-only", {"query": "test"}
        )
        tool_block_only.model_dump.return_value = {
            "type": "tool_use", "name": "search_process_docs",
            "id": "tid-only", "input": {"query": "test"},
        }
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_response(
            "end_turn", [tool_block_only]
        )

        with patch("src.agent.orchestrator.anthropic.Anthropic", return_value=mock_client):
            result = run_agent("test")

        assert result["answer"] != ""
        assert "no text response" in result["answer"].lower() or "rephras" in result["answer"].lower()
