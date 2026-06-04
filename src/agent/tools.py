"""Tool functions + tool schemas + dispatch.

search_process_docs and lookup_known_issues use the hybrid retrieval
layer (BGE-M3 + RRF). get_it_scope and get_escalation_path retain the original
naive keyword lookup — those tools query small, tightly-scoped docs where
semantic retrieval adds no measurable benefit over structured keyword matching.

Each tool returns a typed dict — minimal-privilege: only the fields
the caller needs, not whole-document dumps. JSON-serializable.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from src.agent.doc_loader import Document, get_docs

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def search_process_docs(query: str) -> dict[str, Any]:
    """Search HR process and onboarding documentation for the given query.

    Uses BGE-M3 hybrid+RRF retrieval: semantic-primary pipeline
    over the full M2 policy/process/onboarding corpus (9+ docs, 100+ chunks).
    Falls back to naive keyword search if the retrieval layer is unavailable.

    Returns relevant excerpt, source filename, and section header.
    """
    try:
        from src.retrieval.retriever import get_retriever

        retriever = get_retriever()
        results = retriever.search_process_docs(query, top_k=3)
        if results:
            top = results[0]
            return {
                "found": True,
                "excerpt": top.content[:1500].strip(),
                "source": top.filename,
                "section": top.section_header,
                "doc_title": top.doc_title,
            }
        return {"found": False, "excerpt": "", "source": ""}
    except ImportError:
        # Retrieval layer not installed — the designed fallback (lightweight/CI
        # envs). Expected; info-level.
        logger.info("Retrieval layer not installed — using naive keyword search")
    except Exception:
        # Retrieval IS installed but failed at runtime — a real bug. Fall back to
        # keep the demo responsive, but log at ERROR so the degradation is NOT
        # silent. Note: the naive net covers only the 5 original
        # docs, not the full M2 corpus — degraded, not equivalent.
        logger.error("Retrieval failed at runtime — serving degraded keyword fallback", exc_info=True)

    # Fallback: naive keyword lookup (original behaviour)
    docs = get_docs()
    targets = [
        docs[f]
        for f in ("hr-processes.md", "onboarding-checklist.md")
        if f in docs
    ]
    return _keyword_search(query, targets, max_chars=1500)


def lookup_known_issues(description: str) -> dict[str, Any]:
    """Look up known HR system issues matching the description.

    Uses BGE-M3 hybrid+RRF retrieval: BM25-heavy pipeline over the
    full M2 ITSM ticket corpus (28 incident records + known-issues.md).
    Sparse retrieval leads to ensure exact HR vocabulary matches (PA30, EIB,
    RITM, SAP T-codes) are not lost to dense embedding conflation.
    Falls back to naive keyword search if the retrieval layer is unavailable.

    Returns workaround/fix_status context, source, system_affected, and
    resolution_status — or a "not found" result if no match exists.
    """
    try:
        from src.retrieval.retriever import get_retriever

        retriever = get_retriever()
        results = retriever.lookup_known_issues(description, top_k=3)
        if results:
            top = results[0]
            result: dict[str, Any] = {
                "found": True,
                "excerpt": top.content[:1500].strip(),
                "source": top.filename,
                "doc_title": top.doc_title,
            }
            if top.system_affected:
                result["system_affected"] = top.system_affected
            if top.resolution_status:
                result["resolution_status"] = top.resolution_status
            return result
        return {
            "found": False,
            "excerpt": "",
            "source": "",
            "message": (
                "No known issue matched that description. "
                "Submit a ServiceNow incident if this is a new problem."
            ),
        }
    except ImportError:
        # Retrieval layer not installed — the designed fallback. Expected; info-level.
        logger.info("Retrieval layer not installed — using naive keyword search")
    except Exception:
        # Installed but failed at runtime — a real bug. Fall back for resilience
        # but log at ERROR so the degradation isn't silent. The
        # naive net here is only known-issues.md, not the 28 ITSM records.
        logger.error("Retrieval failed at runtime — serving degraded keyword fallback", exc_info=True)

    # Fallback: naive keyword lookup (original behaviour)
    docs = get_docs()
    if "known-issues.md" not in docs:
        return {"found": False, "message": "Known issues document unavailable."}
    doc = docs["known-issues.md"]
    result = _keyword_search(description, [doc], max_chars=1200)
    if not result["found"]:
        result["message"] = (
            "No known issue matched that description. "
            "Submit a ServiceNow incident if this is a new problem."
        )
    return result


def get_it_scope(domain: str) -> dict[str, Any]:
    """Return the IT team responsible for the given domain and their scope.

    Describes which team owns the domain, their responsibilities,
    and what they explicitly do NOT handle.
    Searches it-scope.md.
    """
    docs = get_docs()
    if "it-scope.md" not in docs:
        return {"found": False, "message": "IT scope document unavailable."}
    doc = docs["it-scope.md"]
    result = _keyword_search(domain, [doc], max_chars=1200)
    if not result["found"]:
        result["message"] = (
            "No IT team found for that domain. "
            "Check it-scope.md or contact hris-support@meridian.com."
        )
    return result


def get_escalation_path(team: str, priority: str) -> dict[str, Any]:
    """Return the escalation path, contact method, and SLA for the given team and priority.

    Priority values: 'P1', 'P2', 'P3', 'P4' (or plain descriptions like 'critical', 'high').
    Returns: contact method, SLA, escalation chain.
    Searches escalation-matrix.md.
    """
    docs = get_docs()
    if "escalation-matrix.md" not in docs:
        return {"found": False, "message": "Escalation matrix unavailable."}
    doc = docs["escalation-matrix.md"]
    combined_query = f"{team} {priority}"
    result = _keyword_search(combined_query, [doc], max_chars=1200)
    if not result["found"]:
        result["message"] = (
            "No escalation path found for that team/priority combination. "
            "Raise a ServiceNow ticket directly."
        )
    return result


# ---------------------------------------------------------------------------
# Naive lookup helper
# ---------------------------------------------------------------------------


_STOPWORDS = frozenset({
    "how", "do", "i", "the", "in", "a", "an", "is", "are", "what", "who",
    "for", "to", "my", "at", "and", "or", "not", "this", "that", "it",
    "be", "was", "with", "me", "we", "you", "can", "will", "its", "if",
    "by", "on", "of", "from", "have", "has", "when", "where", "there",
})


def _keyword_search(
    query: str,
    docs: list[Document],
    max_chars: int = 1500,
) -> dict[str, Any]:
    """Score doc sections by keyword overlap, return best-matching excerpt."""
    raw_tokens = set(query.lower().split())
    query_tokens = raw_tokens - _STOPWORDS
    if not query_tokens:
        query_tokens = raw_tokens  # fallback: all-stopword query

    best_score = 0
    best_excerpt = ""
    best_source = ""

    for doc in docs:
        sections = _split_sections(doc.content)
        for section in sections:
            section_tokens = set(section.lower().split())
            score = len(query_tokens & section_tokens)
            if score > best_score:
                best_score = score
                best_excerpt = section[:max_chars]
                best_source = doc.filename

    if best_score == 0:
        return {"found": False, "excerpt": "", "source": ""}

    return {
        "found": True,
        "excerpt": best_excerpt.strip(),
        "source": best_source,
    }


def _split_sections(content: str) -> list[str]:
    """Split markdown into sections on ## and ### headers."""
    sections: list[str] = []
    current: list[str] = []
    for line in content.splitlines(keepends=True):
        is_header = line.startswith("## ") or line.startswith("### ")
        if is_header and current:
            sections.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("".join(current))
    return sections or [content]


# ---------------------------------------------------------------------------
# Tool schemas (Anthropic tool_use format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_process_docs",
        "description": (
            "Search Meridian HR process and onboarding documentation. "
            "Use this when the user asks HOW to do something in an HR system — "
            "e.g., how to request time off, how to update personal data, "
            "how to submit an expense, how onboarding works. "
            "Returns relevant excerpts and the source document."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A natural-language description of the process or task the user needs help with. "
                        "Example: 'how to request PTO in Workday' or 'expense report submission steps'."
                    ),
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "lookup_known_issues",
        "description": (
            "Look up known Meridian HR system issues, outages, and workarounds. "
            "Use this when the user reports a technical problem, error, or system malfunction — "
            "e.g., 'Workday login is looping', 'my expense receipt OCR failed', "
            "'PA30 is locked'. Returns workaround, fix status, and ticket reference if a match is found."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": (
                        "A description of the technical issue or error the user is experiencing. "
                        "Include the system name and symptom. "
                        "Example: 'Workday SSO loop after password reset' or 'PA30 locked by another user'."
                    ),
                }
            },
            "required": ["description"],
        },
    },
    {
        "name": "get_it_scope",
        "description": (
            "Look up which Meridian IT team owns a given system or domain and what they are responsible for. "
            "Use this when the user wants to know WHO handles something — "
            "e.g., 'who manages Okta', 'which team handles CPI integrations', "
            "'who owns SuccessFactors permissions'. Returns team name, responsibilities, and what they do NOT handle."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": (
                        "The system, technology, or functional area to look up ownership for. "
                        "Example: 'Okta SSO', 'EC to ECP integration', 'SuccessFactors RBP', 'payroll'."
                    ),
                }
            },
            "required": ["domain"],
        },
    },
    {
        "name": "get_escalation_path",
        "description": (
            "Look up the escalation path, contact method, and SLA for a given IT team and priority level. "
            "Use this when the user needs to know HOW TO REACH a team, what the SLA is, "
            "or who to escalate to if the issue is not resolved. "
            "Always use this after get_it_scope identifies the team, or when the user asks "
            "'how do I escalate', 'what is the SLA', 'who do I contact for a P1'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": (
                        "The IT team to retrieve escalation information for. "
                        "Example: 'IAM', 'HRIS', 'Integration', 'Payroll', 'ServiceNow Admin'."
                    ),
                },
                "priority": {
                    "type": "string",
                    "description": (
                        "The priority level of the issue. "
                        "Values: 'P1' (critical/business-stopping), 'P2' (high), "
                        "'P3' (medium/standard), 'P4' (low). "
                        "Use 'P1' for Day-1 provisioning failures or payroll-run blockers."
                    ),
                },
            },
            "required": ["team", "priority"],
        },
    },
]

# Cache-control variant ─────────────────────────────────────────────
# The cache_control on the last tool tells the API that the entire tool list
# (all four definitions — static across every call) is eligible for caching.
# Combined with SYSTEM_PROMPT_CACHED, this covers the full static prefix.
# The first call in a session pays the cache-write cost ($3.75/MTok); every
# subsequent call in the same session reads at $0.30/MTok.
TOOL_DEFINITIONS_CACHED: list[dict[str, Any]] = [
    *TOOL_DEFINITIONS[:-1],
    {**TOOL_DEFINITIONS[-1], "cache_control": {"type": "ephemeral"}},
]

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_TOOL_MAP: dict[str, Callable[..., dict[str, Any]]] = {
    "search_process_docs": search_process_docs,
    "lookup_known_issues": lookup_known_issues,
    "get_it_scope": get_it_scope,
    "get_escalation_path": get_escalation_path,
}


def dispatch_tool(name: str, tool_input: dict[str, Any]) -> str:
    """Call the named tool and return its result as a JSON string.

    Raises on tool failure so the orchestrator's is_error handler fires.
    Unknown tool names return a JSON error string (not an exception —
    they represent a model routing mistake, not a tool runtime failure).
    """
    fn = _TOOL_MAP.get(name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    result = fn(**tool_input)
    return json.dumps(result, ensure_ascii=False)
