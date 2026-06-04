"""Step-level AST evaluator for the HR Ops Agent.

Deterministic scoring — no LLM-as-judge.

Three independently-failing metrics:
  check_tool_usage    — required tools called?       (tool node accuracy)
  check_tool_sequence — called in the right order?   (edge accuracy)
  check_tool_arguments— args contain expected terms? (parameter accuracy)
  check_tool_execution— all calls returned non-error?(execution accuracy)

Failure taxonomy (7-type):
  classify_failure returns one of:
    "none"               — no failure detected
    "planning_error"     — wrong tool selected or wrong sequence
    "tool_misuse"        — correct tool, wrong arguments
    "answer_mismatch"    — answer missing expected content
    "hallucinated_result"— answer contains forbidden content
    "policy_miss"        — out-of-scope query not disclaimed
    "wrong_calculation"  — numeric error (reserved; not triggered by current tools)
    "format_error"       — answer format issue (reserved)

Error-propagation rule: downstream steps depending on an errored call
are marked failed too — check_tool_execution captures this at the call level.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Failure type literals
FAILURE_TYPES = (
    "none",
    "planning_error",
    "tool_misuse",
    "answer_mismatch",
    "hallucinated_result",
    "policy_miss",
    "wrong_calculation",
    "format_error",
)


# Phrases in a golden entry's notes that mark its expected tools as
# order-independent (set membership only, no sequence enforcement).
_ORDER_FLEXIBLE_MARKERS = ("order flexible", "either order", "either tool")

# Answer phrases that indicate the agent refused / disclaimed an out-of-scope
# request. Used to verify requires_refusal golden cases actually refuse.
_REFUSAL_MARKERS = (
    "can't", "cannot", "can not", "unable", "not able", "out of scope",
    "outside my scope", "outside the scope", "read-only", "read only",
    "don't have access", "do not have access", "not able to help",
    "hr business partner", "contact your hr", "i'm not able", "i am not able",
)


def _is_order_flexible(golden: dict[str, Any]) -> bool:
    notes = golden.get("notes", "").lower()
    return any(marker in notes for marker in _ORDER_FLEXIBLE_MARKERS)


def _looks_like_refusal(answer_lower: str) -> bool:
    return any(marker in answer_lower for marker in _REFUSAL_MARKERS)


# ─────────────────────────────────────────────────────────────────────────────
# Step-level checkers
# Each returns (passed: bool, detail: str)
# ─────────────────────────────────────────────────────────────────────────────


def check_tool_usage(
    tools_called: list[str],
    golden: dict[str, Any],
) -> tuple[bool, str]:
    """required_tools ⊆ actual tools called (order-independent)."""
    required = set(golden["required_tools"])
    actual = set(tools_called)
    missing = required - actual
    if missing:
        return False, f"missing_required={sorted(missing)}"
    return True, "ok"


def check_tool_sequence(
    tools_called: list[str],
    golden: dict[str, Any],
) -> tuple[bool, str]:
    """Required tool sequence appears as a subsequence of actual calls.

    The agent is allowed to call extra tools (proactive context-enrichment).
    What we enforce: all required tools are called, in the expected relative order.

    For multi_step queries where order is noted as flexible (notes contains
    "order flexible" or "either order"), only checks set membership.
    """
    expected_seq = [s["tool"] for s in golden["expected_tool_sequence"]]
    order_flexible = _is_order_flexible(golden)

    if order_flexible:
        missing_set = set(expected_seq) - set(tools_called)
        if missing_set:
            return False, f"missing_tools={sorted(missing_set)} (order_flexible=True)"
        return True, "ok (order_flexible=True)"

    # Subsequence check: expected_seq must appear as an ordered subsequence
    # of tools_called (extra tools between/after are allowed).
    ei = 0
    for tool in tools_called:
        if ei < len(expected_seq) and tool == expected_seq[ei]:
            ei += 1
    if ei == len(expected_seq):
        extra = [t for t in tools_called if t not in set(expected_seq)]
        note = f" (extra_tools={extra})" if extra else ""
        return True, f"ok{note}"

    matched = expected_seq[:ei]
    missing = expected_seq[ei:]
    return False, (
        f"subsequence_mismatch: matched={matched} missing={missing} "
        f"actual={tools_called}"
    )


def _match_calls_to_steps(
    expected_steps: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
    order_flexible: bool,
) -> list[dict[str, Any] | None]:
    """Map each expected step to the actual ToolCallDetail it should score against.

    Strict order: walk the actual calls left-to-right, consuming each as it
    satisfies the next expected step of the same tool name. This mirrors the
    subsequence alignment in check_tool_sequence and — critically — handles the
    same tool appearing multiple times with different args (the first-occurrence
    index this replaces scored every repeat against the first call).

    Order-flexible: match each step to the first actual call of that tool, since
    order carries no meaning for those golden entries.
    """
    matched: list[dict[str, Any] | None] = []
    if order_flexible:
        first_by_tool: dict[str, dict[str, Any]] = {}
        for call in tool_calls:
            first_by_tool.setdefault(call["tool"], call)
        return [first_by_tool.get(step["tool"]) for step in expected_steps]

    cursor = 0
    for step in expected_steps:
        tool = step["tool"]
        found: dict[str, Any] | None = None
        for j in range(cursor, len(tool_calls)):
            if tool_calls[j]["tool"] == tool:
                found = tool_calls[j]
                cursor = j + 1
                break
        matched.append(found)
    return matched


def _arg_failures(
    step_index: int,
    expected_step: dict[str, Any],
    actual_call: dict[str, Any],
) -> list[str]:
    """Token-split substring check for one matched (step, call) pair."""
    failures: list[str] = []
    args_contains: dict[str, str] = expected_step.get("args_contains", {})
    for arg_name, expected_substr in args_contains.items():
        actual_val = str(actual_call["args"].get(arg_name, "")).lower()
        expected_lower = expected_substr.lower()

        # Flexible priority matching: "P" sentinel matches any of P1–P4.
        if expected_lower == "p" and any(
            actual_val.startswith(f"p{n}") or f"p{n}" in actual_val
            for n in ("1", "2", "3", "4")
        ):
            continue

        # Token-split: each space-separated term must appear individually
        # (case-insensitive) — more robust than requiring the exact phrase.
        terms = expected_lower.split()
        missing_terms = [t for t in terms if t not in actual_val]
        if missing_terms:
            failures.append(
                f"step_{step_index} arg '{arg_name}': "
                f"missing_terms={missing_terms} in actual='{actual_val}'"
            )
    return failures


def check_tool_arguments(
    tool_calls: list[dict[str, Any]],
    golden: dict[str, Any],
) -> tuple[bool, str]:
    """Per-arg substring check (case-insensitive), positionally aligned.

    Each step in expected_tool_sequence is matched to its corresponding actual
    call (see _match_calls_to_steps), then its args_contains substrings are
    verified token-by-token. A step whose tool was never called fails with a note.
    """
    expected_steps = golden["expected_tool_sequence"]
    matched = _match_calls_to_steps(
        expected_steps, tool_calls, _is_order_flexible(golden)
    )

    failures: list[str] = []
    for i, (expected_step, actual_call) in enumerate(
        zip(expected_steps, matched, strict=True)
    ):
        if actual_call is None:
            failures.append(f"step_{i} ({expected_step['tool']}): tool not called")
            continue
        failures.extend(_arg_failures(i, expected_step, actual_call))

    if failures:
        return False, "; ".join(failures)
    return True, "ok"


def check_tool_execution(
    tool_calls: list[dict[str, Any]],
) -> tuple[bool, str]:
    """All tool calls returned non-error results.

    Checks the raw JSON result string from each call for an 'error' key.
    Error-propagation: any errored call fails this check.
    """
    errors: list[str] = []
    for call in tool_calls:
        result_str = call.get("result", "{}")
        try:
            result_obj = json.loads(result_str)
            if isinstance(result_obj, dict) and "error" in result_obj:
                errors.append(f"{call['tool']}: {result_obj['error']}")
        except (json.JSONDecodeError, ValueError):
            pass  # Non-JSON result is not treated as an error
    if errors:
        return False, "; ".join(errors)
    return True, "ok"


# ─────────────────────────────────────────────────────────────────────────────
# Failure classifier
# ─────────────────────────────────────────────────────────────────────────────


def classify_failure(
    answer: str,
    golden: dict[str, Any],
    usage_ok: bool,
    sequence_ok: bool,
    args_ok: bool,
    execution_ok: bool,
) -> str:
    """Classify failure type for a query that did not achieve a full pass.

    Priority order: routing failures → hallucination → policy refusal → content.
    An out-of-scope golden entry (requires_refusal=True) that routes correctly
    but does not actually refuse is a policy_miss — checked independently of
    expected_answer_contains so the branch is reachable for empty-contains cases.
    """
    answer_lower = answer.lower()

    # Routing failures
    if not usage_ok:
        return "planning_error"
    if not sequence_ok:
        return "planning_error"
    if not args_ok:
        return "tool_misuse"
    if not execution_ok:
        return "tool_misuse"

    # Hallucination: forbidden content present (e.g., a fabricated contact).
    excludes = golden.get("expected_answer_excludes", [])
    if any(s.lower() in answer_lower for s in excludes):
        return "hallucinated_result"

    # Policy refusal: out-of-scope requests must be actively refused, not just
    # routed. Reachable even when expected_answer_contains is empty.
    if golden.get("requires_refusal") and not _looks_like_refusal(answer_lower):
        return "policy_miss"

    # Content mismatch: routed correctly but missing expected answer terms.
    expected_contains = golden.get("expected_answer_contains", [])
    if expected_contains:
        missing_terms = [s for s in expected_contains if s.lower() not in answer_lower]
        if missing_terms:
            return "answer_mismatch"

    return "none"


# ─────────────────────────────────────────────────────────────────────────────
# Task-level result aggregator
# ─────────────────────────────────────────────────────────────────────────────


def evaluate_single(
    result: dict[str, Any],
    golden: dict[str, Any],
    skip_args_check: bool = False,
) -> dict[str, Any]:
    """Run all four checks on a single (result, golden) pair.

    Args:
        result: AgentResult dict (answer, tools_called, tool_calls, turns).
        golden: One entry from the golden set.
        skip_args_check: When True, skip check_tool_arguments and treat as ok.
            Use this when tool_calls is unavailable (e.g., re-scoring from traces).

    Returns a flat dict with all scores + failure class.
    """
    tools_called: list[str] = result.get("tools_called", [])
    tool_calls: list[dict[str, Any]] = result.get("tool_calls", [])
    answer: str = result.get("answer", "")

    usage_ok, usage_detail = check_tool_usage(tools_called, golden)
    sequence_ok, sequence_detail = check_tool_sequence(tools_called, golden)

    if skip_args_check or not tool_calls:
        args_ok, args_detail = True, "skipped (no args data in traces)"
    else:
        args_ok, args_detail = check_tool_arguments(tool_calls, golden)

    exec_ok, exec_detail = check_tool_execution(tool_calls)

    failure_class = classify_failure(
        answer, golden, usage_ok, sequence_ok, args_ok, exec_ok
    )
    passed = failure_class == "none"

    return {
        "id": golden["id"],
        "type": golden["type"],
        "answer_type": golden["answer_type"],
        "required_tools": golden["required_tools"],
        "actual_tools": tools_called,
        "usage_ok": usage_ok,
        "usage_detail": usage_detail,
        "sequence_ok": sequence_ok,
        "sequence_detail": sequence_detail,
        "args_ok": args_ok,
        "args_detail": args_detail,
        "exec_ok": exec_ok,
        "exec_detail": exec_detail,
        "failure_class": failure_class,
        "pass": passed,
        "answer_preview": answer[:120].replace("\n", " "),
    }
