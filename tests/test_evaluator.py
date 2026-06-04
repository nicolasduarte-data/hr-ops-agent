"""Unit tests for the step-level evaluator scoring logic.

This is the code that produces the headline routing/full-pass numbers. Covers
the four checkers, the failure classifier (including the previously-unreachable
policy_miss branch), positional same-tool args alignment, and out-of-scope
refusal handling.
"""

from __future__ import annotations

from typing import Any

from eval.evaluator import (
    check_tool_arguments,
    check_tool_execution,
    check_tool_sequence,
    check_tool_usage,
    classify_failure,
    evaluate_single,
)


def _golden(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "test_001",
        "type": "tool_use",
        "instruction": "test",
        "allowed_tools": [],
        "required_tools": ["search_process_docs"],
        "expected_tool_sequence": [
            {"tool": "search_process_docs", "args_contains": {"query": "time off"}}
        ],
        "expected_answer_contains": [],
        "expected_answer_excludes": [],
        "answer_type": "procedural",
        "notes": "",
        "requires_refusal": False,
    }
    base.update(overrides)
    return base


def _call(tool: str, **args: Any) -> dict[str, Any]:
    return {"tool": tool, "args": args, "result": '{"found": true}'}


class TestCheckToolUsage:
    def test_required_subset_passes(self) -> None:
        ok, _ = check_tool_usage(["search_process_docs", "get_it_scope"], _golden())
        assert ok

    def test_missing_required_fails(self) -> None:
        ok, detail = check_tool_usage(["get_it_scope"], _golden())
        assert not ok
        assert "search_process_docs" in detail


class TestCheckToolSequence:
    def test_subsequence_with_extra_tools_passes(self) -> None:
        g = _golden(
            required_tools=["lookup_known_issues", "get_escalation_path"],
            expected_tool_sequence=[
                {"tool": "lookup_known_issues", "args_contains": {}},
                {"tool": "get_escalation_path", "args_contains": {}},
            ],
        )
        ok, _ = check_tool_sequence(
            ["lookup_known_issues", "get_it_scope", "get_escalation_path"], g
        )
        assert ok

    def test_out_of_order_fails(self) -> None:
        g = _golden(
            expected_tool_sequence=[
                {"tool": "lookup_known_issues", "args_contains": {}},
                {"tool": "get_escalation_path", "args_contains": {}},
            ],
        )
        ok, _ = check_tool_sequence(["get_escalation_path", "lookup_known_issues"], g)
        assert not ok

    def test_order_flexible_ignores_order(self) -> None:
        g = _golden(
            notes="Either tool order acceptable.",
            expected_tool_sequence=[
                {"tool": "get_it_scope", "args_contains": {}},
                {"tool": "lookup_known_issues", "args_contains": {}},
            ],
        )
        ok, _ = check_tool_sequence(["lookup_known_issues", "get_it_scope"], g)
        assert ok


class TestCheckToolArguments:
    def test_token_split_match_passes(self) -> None:
        g = _golden(
            required_tools=["lookup_known_issues"],
            expected_tool_sequence=[
                {"tool": "lookup_known_issues", "args_contains": {"description": "Concur OCR"}}
            ],
        )
        calls = [_call("lookup_known_issues", description="Concur mobile OCR issue")]
        ok, _ = check_tool_arguments(calls, g)
        assert ok

    def test_missing_term_fails(self) -> None:
        g = _golden(
            required_tools=["lookup_known_issues"],
            expected_tool_sequence=[
                {"tool": "lookup_known_issues", "args_contains": {"description": "Concur OCR"}}
            ],
        )
        calls = [_call("lookup_known_issues", description="Workday login loop")]
        ok, _ = check_tool_arguments(calls, g)
        assert not ok

    def test_priority_p_sentinel_matches_p1_through_p4(self) -> None:
        g = _golden(
            required_tools=["get_escalation_path"],
            expected_tool_sequence=[
                {"tool": "get_escalation_path",
                 "args_contains": {"team": "IAM", "priority": "P"}}
            ],
        )
        for level in ("P1", "P2", "P3", "P4"):
            calls = [_call("get_escalation_path", team="IAM", priority=level)]
            ok, _ = check_tool_arguments(calls, g)
            assert ok, level

    def test_same_tool_twice_aligns_positionally(self) -> None:
        # T2-4: two calls of the same tool with different args must each be
        # checked against their OWN call. The old first-occurrence-by-name
        # logic scored both expected steps against the first call, so the
        # second step's "offboarding" term was reported missing.
        g = _golden(
            required_tools=["search_process_docs"],
            expected_tool_sequence=[
                {"tool": "search_process_docs", "args_contains": {"query": "onboarding"}},
                {"tool": "search_process_docs", "args_contains": {"query": "offboarding"}},
            ],
        )
        calls = [
            _call("search_process_docs", query="onboarding checklist"),
            _call("search_process_docs", query="offboarding process"),
        ]
        ok, detail = check_tool_arguments(calls, g)
        assert ok, detail

    def test_uncalled_tool_reports_not_called(self) -> None:
        g = _golden(
            required_tools=["get_it_scope"],
            expected_tool_sequence=[
                {"tool": "get_it_scope", "args_contains": {"domain": "Okta"}}
            ],
        )
        ok, detail = check_tool_arguments([], g)
        assert not ok
        assert "not called" in detail


class TestCheckToolExecution:
    def test_clean_results_pass(self) -> None:
        ok, _ = check_tool_execution([_call("search_process_docs", query="x")])
        assert ok

    def test_error_key_fails(self) -> None:
        calls = [{"tool": "x", "args": {}, "result": '{"error": "boom"}'}]
        ok, detail = check_tool_execution(calls)
        assert not ok
        assert "boom" in detail

    def test_non_json_result_is_not_an_error(self) -> None:
        calls = [{"tool": "x", "args": {}, "result": "plain text not json"}]
        ok, _ = check_tool_execution(calls)
        assert ok


class TestClassifyFailure:
    def test_planning_error_on_bad_usage(self) -> None:
        assert classify_failure("a", _golden(), False, True, True, True) == "planning_error"

    def test_planning_error_on_bad_sequence(self) -> None:
        assert classify_failure("a", _golden(), True, False, True, True) == "planning_error"

    def test_tool_misuse_on_bad_args(self) -> None:
        assert classify_failure("a", _golden(), True, True, False, True) == "tool_misuse"

    def test_tool_misuse_on_bad_exec(self) -> None:
        assert classify_failure("a", _golden(), True, True, True, False) == "tool_misuse"

    def test_hallucinated_on_excludes_hit(self) -> None:
        g = _golden(expected_answer_excludes=["@meridian"])
        out = classify_failure("contact jane@meridian.com", g, True, True, True, True)
        assert out == "hallucinated_result"

    def test_policy_miss_when_refusal_required_but_absent(self) -> None:
        # T1-2: reachable even though expected_answer_contains is empty.
        g = _golden(requires_refusal=True)
        out = classify_failure("The CEO is reachable at HQ.", g, True, True, True, True)
        assert out == "policy_miss"

    def test_none_when_refusal_required_and_present(self) -> None:
        g = _golden(requires_refusal=True)
        out = classify_failure(
            "I can't share that — it's out of scope.", g, True, True, True, True
        )
        assert out == "none"

    def test_excludes_take_priority_over_refusal(self) -> None:
        # A leaked contact is hallucinated_result even on a requires_refusal query.
        g = _golden(requires_refusal=True, expected_answer_excludes=["@meridian"])
        out = classify_failure("sure: ceo@meridian.com", g, True, True, True, True)
        assert out == "hallucinated_result"

    def test_answer_mismatch_on_missing_terms(self) -> None:
        g = _golden(expected_answer_contains=["Workday", "PTO"])
        out = classify_failure("here is some unrelated text", g, True, True, True, True)
        assert out == "answer_mismatch"

    def test_none_on_clean_pass(self) -> None:
        g = _golden(expected_answer_contains=["time off"])
        out = classify_failure("here is how to request time off", g, True, True, True, True)
        assert out == "none"


class TestEvaluateSingle:
    def test_skip_args_check_true(self) -> None:
        result = {
            "answer": "time off info",
            "tools_called": ["search_process_docs"],
            "tool_calls": [],
            "turns": 1,
        }
        row = evaluate_single(result, _golden(), skip_args_check=True)
        assert row["args_ok"] is True
        assert "skipped" in row["args_detail"]

    def test_full_pass_end_to_end(self) -> None:
        g = _golden(expected_answer_contains=["time off"])
        result = {
            "answer": "here is how to request time off",
            "tools_called": ["search_process_docs"],
            "tool_calls": [_call("search_process_docs", query="time off request")],
            "turns": 1,
        }
        row = evaluate_single(result, g)
        assert row["pass"] is True
        assert row["failure_class"] == "none"

    def test_policy_miss_end_to_end(self) -> None:
        # adv_025 shape: routes correctly, never refuses → policy_miss, not pass.
        g = _golden(
            requires_refusal=True,
            expected_tool_sequence=[
                {"tool": "search_process_docs", "args_contains": {"query": "CEO contact"}}
            ],
        )
        result = {
            "answer": "The CEO is John Smith, reachable at the main office.",
            "tools_called": ["search_process_docs"],
            "tool_calls": [_call("search_process_docs", query="CEO contact information")],
            "turns": 1,
        }
        row = evaluate_single(result, g)
        assert row["failure_class"] == "policy_miss"
        assert row["pass"] is False
