"""Streamlit chat UI for the HR Operations Agent.

Shows the synthesized answer AND which tools were called per query, so
every answer shows how it was routed.

Runs in two modes (auto-detected):
- Direct mode (HF Spaces / single-process): calls orchestrator directly
- API mode (local dev with FastAPI running): calls POST /chat via httpx
"""

from __future__ import annotations

import logging
import os

import streamlit as st

logger = logging.getLogger(__name__)

# API mode is opt-in via env var; default is direct orchestrator call.
API_URL = os.getenv("API_URL", "")
USE_API_MODE = bool(API_URL)


# ---------------------------------------------------------------------------
# Eager index warm-up — direct mode only
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="⏳ Warming up the knowledge base — first load only…")
def _load_retriever() -> object:
    """Build the BGE-M3 retrieval index once at app start.

    @st.cache_resource stores the result across Streamlit reruns, so the
    2-5 min BGE-M3 build happens during the initial page load (spinner visible),
    NOT during the user's first query. Subsequent reruns return the cached object
    immediately — no build, no spinner.

    Returns None if the retrieval layer is not installed (keyword fallback active).
    """
    try:
        from src.retrieval.retriever import get_retriever

        return get_retriever()
    except ImportError:
        return None  # Retrieval not installed — keyword fallback active in tools.py
    except Exception:
        # Mirror the API-mode warm-up (_warm_up_index): ANY runtime failure
        # (OOM on free-tier, network blip pulling weights, disk-full, ChromaDB
        # lock) must NOT crash the page. @st.cache_resource does not cache
        # exceptions, so an uncaught error here re-raises on every rerun → a
        # crash loop with no chat input. tools.py catches its own retriever
        # errors and falls back to keyword search, so returning None keeps the
        # demo up in degraded mode and lets the user reach a working input.
        logger.exception(
            "Retrieval warm-up failed in direct mode — keyword fallback active"
        )
        return None


# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Meridian HR Assistant",
    page_icon="🧠",
    layout="centered",
)

# Trigger eager warm-up in direct mode BEFORE rendering the sidebar status, so
# the retrieval-model chip reflects the actually-loaded model on the first run.
# In API mode the FastAPI server handles warm-up via its lifespan hook; this
# call is skipped so Streamlit doesn't also build the index client-side.
_retriever = None
if not USE_API_MODE:
    _retriever = _load_retriever()

# Sidebar — observability + retrieval status. Visible to the developer for
# at-a-glance health; harmless to end-users. Two independent signals:
#   • Langfuse: is tracing initialised, and to WHICH region (region mismatch is
#     the #1 cause of "enabled but no traces land").
#   • Retrieval: which embedding model is actually live, so a silent fallback
#     (BGE-M3 → bge-small → TF-IDF → keyword) is visible, not masked.
with st.sidebar:
    st.markdown("### System status")

    # Langfuse tracing status (+ host region)
    try:
        from src.agent.tracer import get_tracer
        _t = get_tracer()
        if _t.enabled:
            st.success(f"🟢 Langfuse tracing active\n\n`{_t.host}`")
        else:
            st.warning("🟡 Langfuse disabled — keys not set or package not installed")
    except Exception:
        st.error("🔴 Tracer init error")

    # Retrieval model status
    if USE_API_MODE:
        st.info("🔌 Retrieval: API mode (served by FastAPI)")
    else:
        try:
            from src.retrieval.index import peek_model_name
            _model = peek_model_name()
            if _model is None and _retriever is not None:
                # Retriever object exists but the index singleton wasn't peekable
                _model = getattr(_retriever, "model_name", None)
            if _model:
                if "bge-m3" in _model.lower():
                    st.success(f"🟢 Retrieval: {_model}")
                else:
                    st.warning(f"🟡 Retrieval fallback: {_model}")
            else:
                st.warning("🟡 Retrieval: keyword fallback (no embedding model)")
        except Exception:
            st.error("🔴 Retrieval status error")

st.title("Meridian HR Operations Assistant")
st.caption(
    "Ask anything about HR processes, system issues, team ownership, or escalation paths. "
    "This assistant uses only Meridian's internal knowledge base — no live system access."
)

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("tools_called"):
            st.markdown(
                "🔧 **Tools used:** " + ", ".join(f"`{t}`" for t in msg["tools_called"])
            )

if query := st.chat_input("e.g. My Workday access isn't working — who do I call?"):
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            if USE_API_MODE:
                import httpx
                try:
                    resp = httpx.post(
                        f"{API_URL}/chat",
                        json={"query": query},
                        timeout=60.0,
                    )
                    # Distinguish the "still warming up" 503 (expected on cold start)
                    # from other 5xx errors so the UI message is actionable.
                    if resp.status_code == 503:
                        detail = resp.json().get("detail", "")
                        if "warming up" in detail.lower() or "warm" in detail.lower():
                            answer = (
                                "⏳ The knowledge base is warming up on first boot. "
                                "Please retry in ~30 seconds."
                            )
                        else:
                            answer = (
                                "⚠️ The assistant is temporarily unavailable. "
                                "Please try again in a moment."
                            )
                        tools_called = []
                    else:
                        resp.raise_for_status()
                        data = resp.json()
                        answer = data["answer"]
                        tools_called = data.get("tools_called", [])
                except Exception:
                    logger.exception("API-mode request failed")
                    answer = (
                        "⚠️ The assistant is temporarily unavailable. "
                        "Please try again in a moment."
                    )
                    tools_called = []
            else:
                from src.agent.orchestrator import run_agent
                from src.agent.tracer import get_tracer
                try:
                    result = run_agent(query)
                    answer = result["answer"]
                    tools_called = result["tools_called"]
                    get_tracer().flush()  # ensure events are sent immediately
                except Exception:
                    logger.exception("Direct-mode agent call failed")
                    answer = (
                        "⚠️ The assistant is temporarily unavailable. "
                        "Please check the configuration or try again."
                    )
                    tools_called = []

        st.markdown(answer)
        if tools_called:
            st.markdown(
                "🔧 **Tools used:** " + ", ".join(f"`{t}`" for t in tools_called)
            )

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "tools_called": tools_called}
    )

with st.expander("ℹ️ Limitations & Scope"):
    st.markdown(
        """
**This assistant is READ-ONLY.** It cannot:
- Make changes to any HR system (Workday, SuccessFactors, SAP)
- Approve, deny, or process requests
- Access real employee personal data (demo runs on synthetic documents only)
- Provide HR or legal advice on individual employment decisions

**What it can do:** Answer questions about HR processes, known system issues,
IT team ownership, and escalation paths using Meridian's internal knowledge base.

For urgent issues or actions, contact your HR Business Partner or raise a
ServiceNow ticket directly.
        """
    )
