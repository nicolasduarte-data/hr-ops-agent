"""FastAPI app — POST /chat endpoint.

Thin wrapper around the orchestrator. Uses run_agent_async to avoid
blocking the event loop during Anthropic API calls.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.agent.config import ANTHROPIC_API_KEY, LLM_MODEL
from src.agent.orchestrator import AgentResult, run_agent_async

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Startup warm-up state
# ---------------------------------------------------------------------------

# Set when the retrieval index is ready to serve queries.
# /chat checks this — returns 503 while the build is in progress rather than
# letting the first user request silently block for 2-5 min on HF free-tier CPU.
_INDEX_READY = threading.Event()
_INDEX_ERROR: str | None = None  # captured on warm-up failure; surfaced in /health


def _warm_up_index() -> None:
    """Build the retrieval index in a background thread at startup.

    Called from the FastAPI lifespan — fires once per process start. The
    ~30–100 s BGE-M3 build happens here so the first user request never triggers
    an in-request build.

    Always sets _INDEX_READY in the finally block — even on failure — because
    the agent's tool layer has its own keyword-search fallback and can serve
    requests regardless of the retrieval outcome. Errors are surfaced via
    /health without blocking /chat indefinitely.
    """
    global _INDEX_ERROR
    try:
        try:
            from src.retrieval.retriever import get_retriever

            get_retriever()  # load_or_build — the slow part (~30–100 s on CPU)
            logger.info("Retrieval index warm-up complete.")
        except ImportError:
            # Retrieval layer not installed (CI / lightweight env).
            # Tools fall back to keyword search — not a blocker for /chat.
            logger.info(
                "Retrieval layer not installed — warm-up skipped; "
                "keyword fallback will be active."
            )
    except Exception:
        # Installed but failed at runtime. Tools catch their own exceptions and
        # fall back to keyword search, so the agent remains usable; surface the
        # error in /health without blocking /chat.
        logger.exception("Retrieval index warm-up failed — keyword fallback will be active.")
        _INDEX_ERROR = (
            "Retrieval index warm-up failed. "
            "Queries will use keyword fallback. Check server logs."
        )
    finally:
        _INDEX_READY.set()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan: launch index warm-up at startup, flush traces at shutdown."""
    thread = threading.Thread(
        target=_warm_up_index,
        daemon=True,
        name="index-warm-up",
    )
    thread.start()
    yield
    # Shutdown: drain any buffered Langfuse events before the process exits.
    # The warm-up daemon thread exits with the process — nothing to clean there.
    try:
        from src.agent.tracer import get_tracer

        get_tracer().flush()
    except Exception:
        logger.exception("Tracer flush on shutdown failed")


app = FastAPI(
    title="HR Operations Agent",
    description="Claude-native HR self-service agent for Meridian",
    version="1.0.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    query: str


class ChatResponse(BaseModel):
    answer: str
    tools_called: list[str]
    turns: int


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    # Readiness gate: return 503 while the index is still building so
    # callers retry in ~30 s rather than hanging for minutes on a cold-start build.
    if not _INDEX_READY.is_set():
        raise HTTPException(
            status_code=503,
            detail="Knowledge base is warming up. Retry in ~30 s.",
        )

    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")
    try:
        result: AgentResult = await run_agent_async(request.query)
    except anthropic.AuthenticationError:
        raise HTTPException(
            status_code=503,
            detail="Agent unavailable: API key not configured. Contact the administrator.",
        )
    except anthropic.APIConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Agent unavailable: could not connect to the inference API. Try again.",
        )
    except anthropic.RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Rate limit reached. Please wait a moment and try again.",
        )
    except anthropic.InternalServerError:
        # 5xx / 529 Overloaded — transient upstream condition, not our bug.
        raise HTTPException(
            status_code=503,
            detail="Agent unavailable: the inference API is temporarily overloaded. Try again shortly.",
        )
    except Exception:
        # Log the original error before replacing it with a generic 500 —
        # otherwise a production failure leaves no debug trail.
        logger.exception("Unhandled error in /chat")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again.",
        )
    # Flush the trace for this request. Unlike a long-lived worker, a serverless
    # or autoscaled API instance may be frozen/killed between requests before the
    # background consumer drains — an explicit flush guarantees delivery. No-op
    # when tracing is disabled.
    try:
        from src.agent.tracer import get_tracer

        get_tracer().flush()
    except Exception:
        logger.exception("Tracer flush after /chat failed")
    return ChatResponse(
        answer=result["answer"],
        tools_called=result["tools_called"],
        turns=result["turns"],
    )


@app.get("/health")
async def health() -> dict[str, object]:
    # Readiness, not just liveness: report API key config AND index state so a
    # misconfigured deploy or a still-building index is not false-green.
    # Does not make a billable API call.
    response: dict[str, object] = {
        "status": "ok",
        "model": LLM_MODEL,
        "key_configured": bool(ANTHROPIC_API_KEY),
        "index_ready": _INDEX_READY.is_set(),
    }
    if _INDEX_ERROR:
        response["index_error"] = _INDEX_ERROR
    return response
