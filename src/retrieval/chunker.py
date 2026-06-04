"""Paragraph-group semantic chunker for HR documents.

Two document shapes, two strategies:
  • Policy / process docs  → section-based chunks (~256–512 tokens each).
    Split on ## headers; further split oversized sections on blank lines.
    HR edge cases handled: tables stay with their header section; FAQ Q&A
    pairs and numbered procedures are kept together within a section.

  • ITSM incident records  → one atomic unit per file.
    inc-*.md files are 30–60 lines each — well inside the 512-token window
    and must not be fragmented (workaround + root-cause + resolution form
    one logical unit). Parse system_affected / resolution_status from the
    structured frontmatter.

Chunks carry metadata required for the two retrieval architectures:
  All chunks: doc_title, doc_type, filename, last_updated_date, section_header
  Ticket chunks: additionally system_affected, resolution_status
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# -----------------------------------------------------------------------
# Types
# -----------------------------------------------------------------------

DocType = Literal["process", "onboarding", "known_issue", "it_scope", "escalation"]

# Maximum characters per chunk ≈ 512 tokens at ~4 chars/token
_MAX_CHUNK_CHARS: int = 2000

# Files that are ITSM incident records → atomic chunk strategy
_INCIDENT_PREFIX = "inc-"

# Filename → doc_type mapping for non-incident files.
# Unmapped filenames → "process" (covers all new M2 policy docs).
_FILENAME_DOC_TYPE: dict[str, DocType] = {
    "hr-processes.md": "process",
    "onboarding-checklist.md": "onboarding",
    "known-issues.md": "known_issue",
    "it-scope.md": "it_scope",
    "escalation-matrix.md": "escalation",
}


# -----------------------------------------------------------------------
# Chunk dataclass
# -----------------------------------------------------------------------

@dataclass
class Chunk:
    chunk_id: str            # "{filename}::{idx}"
    doc_title: str
    doc_type: DocType
    filename: str
    last_updated_date: str
    section_header: str      # nearest ## heading, or "" for atomic ticket records
    content: str
    # Ticket-only metadata (empty string for non-ticket chunks)
    system_affected: str = ""
    resolution_status: str = ""


# -----------------------------------------------------------------------
# Public interface
# -----------------------------------------------------------------------

def chunk_document(content: str, filename: str) -> list[Chunk]:
    """Return all Chunk objects for a single document file."""
    stem = filename.lower()
    if stem.startswith(_INCIDENT_PREFIX):
        return _chunk_incident(content, filename)
    return _chunk_policy_doc(content, filename)


def chunk_directory(docs_dir: Path) -> list[Chunk]:
    """Chunk all .md files in docs_dir (excluding provenance.md)."""
    all_chunks: list[Chunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        if path.name == "provenance.md":
            continue
        content = path.read_text(encoding="utf-8")
        all_chunks.extend(chunk_document(content, path.name))
    return all_chunks


# -----------------------------------------------------------------------
# Incident record chunker (atomic)
# -----------------------------------------------------------------------

def _chunk_incident(content: str, filename: str) -> list[Chunk]:
    title = _extract_title(content) or filename
    doc_type: DocType = "known_issue"
    last_updated = _parse_incident_date(content)
    system_affected = _parse_frontmatter_field(content, "system_affected")
    resolution_status = _parse_frontmatter_field(content, "resolution_status")

    return [
        Chunk(
            chunk_id=f"{filename}::0",
            doc_title=title,
            doc_type=doc_type,
            filename=filename,
            last_updated_date=last_updated,
            section_header="",
            content=content.strip(),
            system_affected=system_affected,
            resolution_status=resolution_status,
        )
    ]


# -----------------------------------------------------------------------
# Policy / process doc chunker (section-based)
# -----------------------------------------------------------------------

def _chunk_policy_doc(content: str, filename: str) -> list[Chunk]:
    doc_type: DocType = _FILENAME_DOC_TYPE.get(filename, "process")
    doc_title = _extract_title(content) or filename
    last_updated = _parse_last_updated(content)

    raw_sections = _split_on_h2(content)
    chunks: list[Chunk] = []

    for header, body in raw_sections:
        section_text = (f"{header}\n\n{body}".strip() if header else body.strip())
        if not section_text:
            continue
        # Split oversized sections on paragraph breaks
        sub_sections = _split_oversized(section_text)
        for sub in sub_sections:
            if not sub.strip():
                continue
            idx = len(chunks)
            chunks.append(
                Chunk(
                    chunk_id=f"{filename}::{idx}",
                    doc_title=doc_title,
                    doc_type=doc_type,
                    filename=filename,
                    last_updated_date=last_updated,
                    section_header=header.lstrip("#").strip() if header else "",
                    content=sub.strip(),
                )
            )

    # Fallback: if no sections found, treat the whole doc as one chunk
    if not chunks:
        chunks.append(
            Chunk(
                chunk_id=f"{filename}::0",
                doc_title=doc_title,
                doc_type=doc_type,
                filename=filename,
                last_updated_date=last_updated,
                section_header="",
                content=content.strip(),
            )
        )
    return chunks


# -----------------------------------------------------------------------
# Splitting helpers
# -----------------------------------------------------------------------

def _split_on_h2(content: str) -> list[tuple[str, str]]:
    """Split markdown on ## headers. Returns (header_line, body) pairs.

    The text before the first ## header (frontmatter / title block) becomes
    a (header="", body=<preamble>) pair at position 0 — kept even if small
    so that doc-level metadata is always retrievable.
    """
    lines = content.splitlines(keepends=True)
    sections: list[tuple[str, str]] = []
    current_header = ""
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## ") and not line.startswith("### "):
            if current_lines:
                sections.append((current_header, "".join(current_lines)))
            current_header = line.rstrip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines or current_header:
        sections.append((current_header, "".join(current_lines)))

    return sections


def _split_oversized(text: str) -> list[str]:
    """Split text that exceeds _MAX_CHUNK_CHARS on blank-line paragraph breaks.

    Tables and indented blocks are kept with their preceding paragraph —
    a blank line inside a table or code fence does NOT split.
    """
    if len(text) <= _MAX_CHUNK_CHARS:
        return [text]

    paragraphs = re.split(r"\n{2,}", text)
    parts: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para) + 2  # +2 for the \n\n we stripped
        if current_len + para_len > _MAX_CHUNK_CHARS and current_parts:
            parts.append("\n\n".join(current_parts))
            current_parts = [para]
            current_len = para_len
        else:
            current_parts.append(para)
            current_len += para_len

    if current_parts:
        parts.append("\n\n".join(current_parts))

    return parts


# -----------------------------------------------------------------------
# Metadata parsing helpers
# -----------------------------------------------------------------------

def _extract_title(content: str) -> str:
    for line in content.splitlines():
        if line.startswith("# ") and not line.startswith("## "):
            return line.lstrip("# ").strip()
    return ""


def _parse_last_updated(content: str) -> str:
    """Parse 'Last updated' from policy doc frontmatter."""
    for line in content.splitlines():
        if "last updated" in line.lower():
            # Handle both '**Last updated**: YYYY-MM-DD' and 'Last Updated: YYYY-MM-DD'
            parts = line.split(":", 1)
            if len(parts) >= 2:
                val = parts[1].strip().lstrip("*").strip()
                # Strip trailing pipe (table separator) or bold markers
                val = val.split("|")[0].strip().strip("*").strip()
                if val:
                    return val
    return "unknown"


def _parse_incident_date(content: str) -> str:
    """Use resolved_date if present, else reported_date, else 'unknown'."""
    resolved = _parse_frontmatter_field(content, "resolved_date")
    if resolved:
        return resolved
    reported = _parse_frontmatter_field(content, "reported_date")
    return reported or "unknown"


def _parse_frontmatter_field(content: str, field_name: str) -> str:
    """Parse '**field_name**: value' from ITSM ticket frontmatter (first 20 lines)."""
    pattern = re.compile(
        r"^\*\*" + re.escape(field_name) + r"\*\*\s*:\s*(.+)$",
        re.IGNORECASE,
    )
    for line in content.splitlines()[:20]:
        m = pattern.match(line.strip())
        if m:
            return m.group(1).strip()
    return ""
