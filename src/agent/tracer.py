"""Optional Langfuse tracing integration.

All functions are no-ops when:
  - langfuse is not installed, OR
  - LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are not set in the environment.

Import freely — this module never raises on import or initialisation.

Usage
-----
::

    from src.agent.tracer import get_tracer

    tracer = get_tracer()
    handle = tracer.start_trace(user_query)

    gen = tracer.start_generation(handle, turn=1, model=MODEL, messages=msgs)
    response = client.messages.create(...)
    tracer.end_generation(gen, handle, response, output_text="...")

    tspan = tracer.start_tool_span(handle, "search_process_docs", args)
    result = dispatch_tool(...)
    tracer.end_tool_span(tspan, result)

    tracer.end_trace(handle, answer, tools_called)
    # handle.usage.as_dict() → {"input_tokens": N, ..., "estimated_cost_usd": 0.00023}

Token accounting runs even when Langfuse is disabled — handle.usage.as_dict()
is always populated and included in AgentResult.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sonnet 4-6 pricing (USD per token — June 2026)
# Update if the model or Anthropic pricing changes.
# ---------------------------------------------------------------------------
_INPUT_COST_PER_TOK: float = 3.00 / 1_000_000    # $3.00 / MTok
_OUTPUT_COST_PER_TOK: float = 15.00 / 1_000_000  # $15.00 / MTok
_CACHE_WRITE_PER_TOK: float = 3.75 / 1_000_000   # $3.75 / MTok — cache_creation
_CACHE_READ_PER_TOK: float = 0.30 / 1_000_000    # $0.30 / MTok — cache_read (10× cheaper)


def _safe_int(val: Any) -> int:
    """Return int(val), or 0 on TypeError/ValueError.

    Needed because MagicMock objects in tests pass attribute access and return
    another MagicMock — int(MagicMock()) raises TypeError which we catch here.
    """
    try:
        return int(val) if val is not None else 0
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Token accounting
# ---------------------------------------------------------------------------


@dataclass
class TokenUsage:
    """Accumulated token counts + cost estimate for a single agent run.

    Updated by tracer.end_generation() on every LLM turn, regardless of
    whether Langfuse is enabled.  Always available in AgentResult["token_usage"].
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0  # tokens written to prompt cache this turn
    cache_read_tokens: int = 0      # tokens served from prompt cache (cheap reads)

    def add_turn(self, usage: Any) -> None:
        """Accumulate counts from one Anthropic API response.usage object."""
        self.input_tokens += _safe_int(getattr(usage, "input_tokens", 0))
        self.output_tokens += _safe_int(getattr(usage, "output_tokens", 0))
        self.cache_creation_tokens += _safe_int(
            getattr(usage, "cache_creation_input_tokens", 0)
        )
        self.cache_read_tokens += _safe_int(
            getattr(usage, "cache_read_input_tokens", 0)
        )

    @property
    def total_cost_usd(self) -> float:
        """Estimated total cost for this agent run in USD."""
        return (
            self.input_tokens * _INPUT_COST_PER_TOK
            + self.output_tokens * _OUTPUT_COST_PER_TOK
            + self.cache_creation_tokens * _CACHE_WRITE_PER_TOK
            + self.cache_read_tokens * _CACHE_READ_PER_TOK
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialisable summary — included in AgentResult and Langfuse trace output."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "estimated_cost_usd": round(self.total_cost_usd, 6),
        }


# ---------------------------------------------------------------------------
# Trace handle
# ---------------------------------------------------------------------------


@dataclass
class TraceHandle:
    """Carries live Langfuse trace context through one agent run.

    Created by Tracer.start_trace(); passed through all subsequent tracer
    calls.  token_usage is populated even when Langfuse is disabled.
    """

    trace_obj: Any  # langfuse StatefulTraceClient | None
    usage: TokenUsage = field(default_factory=TokenUsage)


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------


class Tracer:
    """Thin Langfuse wrapper.  All public methods are no-ops when disabled.

    The singleton is constructed once at import time via get_tracer().
    Langfuse is disabled when:
      - langfuse is not installed
      - LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY are absent or empty
    """

    def __init__(self) -> None:
        self._lf: Any = None
        self._enabled: bool = False
        self._host: str = ""
        self._init()

    def _init(self) -> None:
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
        if not (public_key and secret_key):
            logger.info(
                "Langfuse tracing disabled — LANGFUSE_PUBLIC_KEY/SECRET_KEY not set. "
                "Token accounting still active."
            )
            return
        try:
            from langfuse import Langfuse

            host = os.getenv("LANGFUSE_HOST", "").strip()
            if not host:
                logger.warning(
                    "LANGFUSE_HOST not set — defaulting to https://cloud.langfuse.com. "
                    "If your project is on the US region, set LANGFUSE_HOST="
                    "https://us.cloud.langfuse.com to avoid silent trace loss."
                )
                host = "https://cloud.langfuse.com"
            self._lf = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
            self._enabled = True
            self._host = host
            logger.info("Langfuse tracing enabled → %s", host)
        except ImportError:
            logger.info("langfuse package not installed — tracing disabled.")
        except Exception:
            logger.exception("Langfuse init failed — tracing disabled.")

    # ── Trace lifecycle ────────────────────────────────────────────────────

    def start_trace(self, query: str) -> TraceHandle:
        """Open a new trace for one agent run.

        Always returns a TraceHandle — trace_obj is None if Langfuse is disabled.
        """
        handle = TraceHandle(trace_obj=None)
        if not self._enabled:
            return handle
        try:
            handle.trace_obj = self._lf.trace(
                name="hr-agent-query",
                input={"query": query},
            )
        except Exception:
            logger.exception("Langfuse trace start failed — continuing without trace.")
        return handle

    def end_trace(
        self,
        handle: TraceHandle,
        answer: str,
        tools_called: list[str],
    ) -> None:
        """Close the trace and attach the final answer + accumulated usage."""
        if not self._enabled or handle.trace_obj is None:
            return
        try:
            handle.trace_obj.update(
                output={
                    "answer": answer,
                    "tools_called": tools_called,
                    **handle.usage.as_dict(),
                }
            )
        except Exception:
            logger.exception("Langfuse trace end failed.")

    # ── LLM generation spans ────────────────────────────────

    def start_generation(
        self,
        handle: TraceHandle,
        turn: int,
        model: str,
        messages: list[dict[str, Any]],
    ) -> Any:
        """Open a generation span for one LLM API call.

        Returns the span object, or None when Langfuse is disabled.
        Pass the return value to end_generation().
        """
        if not self._enabled or handle.trace_obj is None:
            return None
        try:
            return handle.trace_obj.generation(
                name=f"llm-turn-{turn}",
                model=model,
                input=messages,
            )
        except Exception:
            logger.exception("Langfuse generation start failed.")
            return None

    def end_generation(
        self,
        gen_span: Any,
        handle: TraceHandle,
        response: Any,
        output_text: str,
    ) -> None:
        """Close a generation span and accumulate token usage.

        Token accumulation runs regardless of Langfuse state — handle.usage
        is always up to date after this call.

        Args:
            gen_span:    Span returned by start_generation() — may be None.
            handle:      Active TraceHandle for this run.
            response:    Anthropic Messages API response object.
            output_text: Human-readable summary of this turn's output
                         (final text for end_turn, tool list for tool_use).
        """
        # Always accumulate — even when Langfuse is disabled.
        usage = getattr(response, "usage", None) if response is not None else None
        if usage is not None:
            handle.usage.add_turn(usage)

        if not self._enabled or gen_span is None:
            return

        try:
            inp = _safe_int(getattr(usage, "input_tokens", 0)) if usage else 0
            out = _safe_int(getattr(usage, "output_tokens", 0)) if usage else 0
            cw = _safe_int(getattr(usage, "cache_creation_input_tokens", 0)) if usage else 0
            cr = _safe_int(getattr(usage, "cache_read_input_tokens", 0)) if usage else 0
            turn_cost = (
                inp * _INPUT_COST_PER_TOK
                + out * _OUTPUT_COST_PER_TOK
                + cw * _CACHE_WRITE_PER_TOK
                + cr * _CACHE_READ_PER_TOK
            )
            usage_dict: dict[str, Any] = {
                "input": inp,
                "output": out,
                "unit": "TOKENS",
            }
            if cw:
                usage_dict["cache_creation_input_tokens"] = cw
            if cr:
                usage_dict["cache_read_input_tokens"] = cr

            gen_span.end(
                output=output_text,
                usage=usage_dict,
                metadata={
                    "stop_reason": getattr(response, "stop_reason", None),
                    "turn_cost_usd": round(turn_cost, 6),
                },
            )
        except Exception:
            logger.exception("Langfuse generation end failed.")

    # ── Tool spans ──────────────────────────────────────────────────

    def start_tool_span(
        self,
        handle: TraceHandle,
        tool_name: str,
        args: dict[str, Any],
    ) -> Any:
        """Open a span for one tool invocation.

        Returns the span object, or None when Langfuse is disabled.
        Pass the return value to end_tool_span().
        """
        if not self._enabled or handle.trace_obj is None:
            return None
        try:
            return handle.trace_obj.span(
                name=f"tool-{tool_name}",
                input={"tool": tool_name, "args": args},
            )
        except Exception:
            logger.exception("Langfuse tool span start failed.")
            return None

    def end_tool_span(
        self,
        span: Any,
        result: str,
        *,
        is_error: bool = False,
    ) -> None:
        """Close a tool span."""
        if not self._enabled or span is None:
            return
        try:
            span.end(
                output={"result": result, "is_error": is_error},
                level="ERROR" if is_error else "DEFAULT",
            )
        except Exception:
            logger.exception("Langfuse tool span end failed.")

    # ── Process lifecycle ──────────────────────────────────────────────────

    def flush(self) -> None:
        """Flush pending Langfuse events.

        Call at process shutdown (FastAPI lifespan teardown / Streamlit exit).
        No-op when disabled.
        """
        if not self._enabled or self._lf is None:
            return
        try:
            self._lf.flush()
        except Exception:
            logger.exception("Langfuse flush failed.")

    @property
    def enabled(self) -> bool:
        """True when Langfuse is configured and traces are being sent."""
        return self._enabled

    @property
    def host(self) -> str:
        """The Langfuse host events are sent to. Empty when disabled.

        Surfaced in the UI so a region mismatch (US project vs. EU default) is
        visible — the most common cause of 'tracing enabled but no traces land'.
        """
        return self._host


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    """Return the module-level Tracer singleton.

    Constructed once on first call.  Thread-safe in practice because Python's
    GIL serialises the assignment — and the worst race outcome is two Tracer
    instances where the second overwrites the first (both are equivalent).
    """
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer
