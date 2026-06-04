"""Hardened tool-use orchestrator loop with optional Langfuse tracing.

Implements the native Anthropic Messages API tool-use loop with:
- Parallel tool_use block handling (all results in one user message)
- model_dump() serialization of assistant turns
- MAX_TURNS guard against infinite loops
- is_error: True on tool exception (dispatch_tool re-raises, not catches)
- stop_reason handling: end_turn / tool_use / max_tokens / other
- Empty tool_results guard (API requires ≥1 item in content list)
- Optional Langfuse spans: one generation per LLM call + one span per tool call
- TokenUsage accumulated every turn; always present in AgentResult["token_usage"]
- Prompt caching: SYSTEM_PROMPT_CACHED + TOOL_DEFINITIONS_CACHED
"""

from __future__ import annotations

import asyncio
import json
import logging
from functools import partial
from typing import Any, TypedDict

import anthropic

from src.agent.config import ANTHROPIC_API_KEY, LLM_MODEL, MAX_TURNS
from src.agent.prompts import SYSTEM_PROMPT_CACHED, SYSTEM_PROMPT_UNDEFENDED
from src.agent.tools import TOOL_DEFINITIONS_CACHED, dispatch_tool
from src.agent.tracer import TraceHandle, get_tracer

logger = logging.getLogger(__name__)

MessageContent = list[dict[str, object]]

# Bound API-call latency so the direct-mode Streamlit UI (HF Spaces default)
# cannot hang indefinitely on a slow or stalled request.
CLIENT_TIMEOUT_S = 60.0
CLIENT_MAX_RETRIES = 2


class ToolCallDetail(TypedDict):
    """Full record of one tool invocation — tool name, arguments, raw result."""

    tool: str
    args: dict[str, object]
    result: str  # raw JSON string returned by dispatch_tool (or error JSON)


class AgentResult(TypedDict):
    answer: str
    tools_called: list[str]       # tool names in call order — used by UI transparency layer
    tool_calls: list[ToolCallDetail]  # full per-call detail — used by eval harness
    turns: int
    token_usage: dict[str, Any]   # token counts + estimated_cost_usd


def _build_result(
    handle: TraceHandle,
    answer: str,
    tools_called: list[str],
    tool_calls: list[ToolCallDetail],
    turns: int,
) -> AgentResult:
    """Construct the AgentResult, close the trace, and return.

    Single exit point for all run_agent return paths — ensures the Langfuse
    trace is always closed and token_usage is always populated.
    """
    tracer = get_tracer()
    tracer.end_trace(handle, answer, tools_called)
    return {
        "answer": answer,
        "tools_called": tools_called,
        "tool_calls": tool_calls,
        "turns": turns,
        "token_usage": handle.usage.as_dict(),
    }


def run_agent(user_query: str, *, undefended: bool = False) -> AgentResult:
    """Run the agent for a single user query (synchronous).

    Callers in async contexts should use run_agent_async() to avoid
    blocking the event loop during Anthropic API calls.

    Args:
        user_query: The user's question or request.
        undefended: If True, use the stripped system prompt (no untrusted-content
            rule, no role lock) and skip the JSON envelope on tool results.
            Used ONLY by the adversarial harness (--undefended flag) to produce
            the naive baseline for before/after ASR comparison.
            Never set to True in production or the public demo.

    Returns a dict with:
      - answer: str — the final synthesized response
      - tools_called: list[str] — names of tools invoked (for UI transparency)
      - tool_calls: list[ToolCallDetail] — full per-call detail (for eval harness)
      - turns: int — how many loop iterations ran
      - token_usage: dict — token counts and estimated_cost_usd
    """
    # Constructed per call to keep the orchestrator unit-testable (tests patch
    # anthropic.Anthropic). timeout + max_retries bound UI hangs — the direct
    # Streamlit path has no outer timeout, unlike the httpx API path.
    client = anthropic.Anthropic(
        api_key=ANTHROPIC_API_KEY,
        timeout=CLIENT_TIMEOUT_S,
        max_retries=CLIENT_MAX_RETRIES,
    )

    tracer = get_tracer()
    handle = tracer.start_trace(user_query)

    messages: list[dict[str, object]] = [
        {"role": "user", "content": user_query}
    ]
    tools_called: list[str] = []
    all_tool_calls: list[ToolCallDetail] = []
    turns = 0

    while turns < MAX_TURNS:
        turns += 1

        # ── LLM call — open generation span before, close after ──────────
        gen_span = tracer.start_generation(handle, turns, LLM_MODEL, messages)

        # Undefended mode uses a stripped system prompt (no D1/D2 defenses)
        # so the naive baseline ASR is measurable. Production always uses the
        # defended cached variant.
        system_prompt: object = (
            SYSTEM_PROMPT_UNDEFENDED if undefended else SYSTEM_PROMPT_CACHED
        )
        # The Anthropic SDK's create() is heavily overloaded and its system /
        # tools / messages params are TypedDicts; our plain dict[str, Any]
        # structures don't match any overload under strict mypy. This is a known
        # SDK/mypy friction point — suppress the single call-overload error at
        # the call site rather than scatter per-arg ignores (the error code moved
        # from arg-type → call-overload when the anthropic stubs were updated).
        response = client.messages.create(  # type: ignore[call-overload]
            model=LLM_MODEL,
            max_tokens=2048,
            system=system_prompt,
            tools=TOOL_DEFINITIONS_CACHED,      # cached tool definitions
            messages=messages,
        )

        logger.debug("Turn %d: stop_reason=%s", turns, response.stop_reason)

        # Serialize assistant turn using model_dump() for correct round-trip
        messages.append(
            {
                "role": "assistant",
                "content": [b.model_dump() for b in response.content],
            }
        )

        if response.stop_reason == "end_turn":
            answer = _extract_text(response)
            # Close generation span with final answer text
            tracer.end_generation(gen_span, handle, response, output_text=answer)
            return _build_result(handle, answer, tools_called, all_tool_calls, turns)

        if response.stop_reason in ("max_tokens", None):
            msg = "The response was cut off. Please try a more specific question."
            tracer.end_generation(
                gen_span, handle, response, output_text=f"max_tokens: {response.stop_reason}"
            )
            return _build_result(handle, msg, tools_called, all_tool_calls, turns)

        if response.stop_reason != "tool_use":
            msg = f"Unexpected stop reason: {response.stop_reason}"
            tracer.end_generation(
                gen_span, handle, response, output_text=msg
            )
            return _build_result(handle, msg, tools_called, all_tool_calls, turns)

        # ── tool_use turn — dispatch all tool_use blocks ─────────────────
        # Close generation span with the list of requested tools
        requested_tools = [
            b.name for b in response.content if b.type == "tool_use"
        ]
        tracer.end_generation(
            gen_span,
            handle,
            response,
            output_text=f"tool_use: {requested_tools}",
        )

        # Collect all tool_use blocks and batch results in ONE user message
        tool_results: MessageContent = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            tools_called.append(block.name)
            args = dict(block.input)

            # Open a span per tool dispatch
            tspan = tracer.start_tool_span(handle, block.name, args)
            try:
                # JSON-encode the retrieved content — untrusted data must not be
                # interpreted as instructions by the model.
                # dispatch_tool now re-raises on tool failure so is_error fires correctly.
                raw_result = dispatch_tool(block.name, args)
                # D3: JSON-envelope isolates retrieved content from the instruction
                # stream. Skipped in undefended mode to measure
                # what ASR would be without structural isolation.
                result_content = (
                    raw_result
                    if undefended
                    else json.dumps({"data": json.loads(raw_result)})
                )
                all_tool_calls.append(
                    {"tool": block.name, "args": args, "result": raw_result}
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content,
                    }
                )
                tracer.end_tool_span(tspan, raw_result)
            except Exception as exc:
                logger.exception("Tool %s raised an exception", block.name)
                error_json = json.dumps({"error": str(exc)})
                all_tool_calls.append(
                    {"tool": block.name, "args": args, "result": error_json}
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "is_error": True,
                        "content": error_json,
                    }
                )
                tracer.end_tool_span(tspan, error_json, is_error=True)

        # Guard: the API requires content list to have at least 1 item.
        # stop_reason=tool_use with no tool_use blocks violates the API contract.
        if not tool_results:
            logger.error(
                "stop_reason=tool_use but no tool_use blocks in response (turn %d); "
                "block types: %s",
                turns,
                [b.type for b in response.content],
            )
            msg = (
                "An unexpected error occurred during tool dispatch. "
                "Please try again."
            )
            return _build_result(handle, msg, tools_called, all_tool_calls, turns)

        messages.append({"role": "user", "content": tool_results})

    msg = "Maximum turn limit reached. Please try a more focused question."
    return _build_result(handle, msg, tools_called, all_tool_calls, turns)


async def run_agent_async(user_query: str) -> AgentResult:
    """Async wrapper — runs run_agent in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(run_agent, user_query))


def _extract_text(response: anthropic.types.Message) -> str:
    # Concatenate ALL text blocks. Returning only the first silently truncates
    # multi-block answers — and the system prompt puts the source citation at
    # the END, so a split answer would drop exactly the citation.
    texts = [block.text for block in response.content if block.type == "text"]
    if texts:
        return "\n\n".join(texts)
    logger.warning(
        "end_turn response had no text block; block types: %s",
        [b.type for b in response.content],
    )
    return (
        "(The agent completed but produced no text response. "
        "Please try rephrasing your question.)"
    )
