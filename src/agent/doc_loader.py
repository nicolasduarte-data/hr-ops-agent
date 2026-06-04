"""Loads synthetic HR documents into memory at startup.

Returns structured doc objects with metadata. This interface
is replaced by a vector-backed retriever — callers see the same schema.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

DocType = Literal["process", "known_issue", "it_scope", "escalation", "onboarding"]

DOCS_DIR = Path(__file__).parent.parent.parent / "synthetic-docs"

DOC_MANIFEST: dict[str, DocType] = {
    "hr-processes.md": "process",
    "known-issues.md": "known_issue",
    "it-scope.md": "it_scope",
    "escalation-matrix.md": "escalation",
    "onboarding-checklist.md": "onboarding",
}


@dataclass
class Document:
    doc_title: str
    doc_type: DocType
    filename: str
    last_updated_date: str
    content: str
    section_headers: list[str] = field(default_factory=list)


def _parse_last_updated(content: str) -> str:
    for line in content.splitlines():
        if "last updated" in line.lower():
            parts = line.split(":")
            if len(parts) >= 2:
                # Strip markdown bold markers (**) that surround the date field
                return parts[1].strip().lstrip("*").strip().split("|")[0].strip()
    return "unknown"


def _extract_section_headers(content: str) -> list[str]:
    return [
        line.lstrip("#").strip()
        for line in content.splitlines()
        if line.startswith("## ")
    ]


def load_documents(docs_dir: Path = DOCS_DIR) -> dict[str, Document]:
    """Load all synthetic docs from disk. Keyed by filename stem."""
    docs: dict[str, Document] = {}
    for filename, doc_type in DOC_MANIFEST.items():
        path = docs_dir / filename
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        title_line = next(
            (ln for ln in content.splitlines() if ln.startswith("# ")),
            filename,
        )
        docs[filename] = Document(
            doc_title=title_line.lstrip("# ").strip(),
            doc_type=doc_type,
            filename=filename,
            last_updated_date=_parse_last_updated(content),
            content=content,
            section_headers=_extract_section_headers(content),
        )
    return docs


_DOCS: dict[str, Document] | None = None
_DOCS_LOCK = threading.Lock()


def get_docs() -> dict[str, Document]:
    # Double-checked locking: run_agent_async dispatches through a thread pool,
    # so concurrent cold-start callers could otherwise both load from disk.
    global _DOCS
    if _DOCS is None:
        with _DOCS_LOCK:
            if _DOCS is None:
                _DOCS = load_documents()
    return _DOCS
