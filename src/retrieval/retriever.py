"""Hybrid retriever with Reciprocal Rank Fusion (RRF).

Two distinct retrieval architectures:

  search_process_docs  → pure dense (semantic)
    Dense retrieval only; sparse weight = 0.0.
    Process docs use natural language with semantic variation — "how to update
    my address" should match "Updating Personal Data" with zero lexical overlap.
    BGE-M3 dense handles this natively. A/B testing showed
    sparse contribution actively degrades process MRR@5 (0.798 hybrid → 0.855
    pure dense). Sparse adds noise, not signal, for natural-language queries
    over natural-language docs.
    Metadata pre-filter: doc_type in ["process", "onboarding"]
    Optional: filter on last_updated_date for recency-sensitive queries.

  lookup_known_issues  → BM25-heavy atomic records
    Sparse retrieval leads; dense retrieval contributes.
    Weighted: 30% dense rank + 70% sparse rank in RRF.
    ITSM ticket records use controlled vocabulary: PA30, EIB, RITM, SAP T-codes,
    Workday module names. Dense models conflate acronyms (EIB ≈ bank → wrong).
    Sparse (BM25-style) scoring weights exact token matches — exactly what HR
    system vocabulary requires.
    Metadata pre-filter: doc_type == "known_issue"
    Optional: filter on system_affected and/or resolution_status.

RRF formula (Cormack et al., 2009):
    rrf_score = Σ weight_i / (k + rank_i + 1)
    where k=60 (the standard value).

The two pipelines use deliberately different retrieval strategies; the per-pipeline
docstrings explain why each fits its document shape.

Why the difference matters:
  Process docs use natural language with semantic variation — a query about
  "how to update my address" should match a section titled "Updating Personal
  Data" even with zero lexical overlap. Dense retrieval handles this.

  ITSM ticket records use controlled vocabulary: PA30, EIB, RITM, SAP T-codes,
  Workday module names. Dense models conflate acronyms (EIB ≈ bank → wrong).
  Sparse (BM25-style) scoring weights exact token matches — exactly what HR
  system vocabulary requires.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.retrieval.chunker import Chunk
from src.retrieval.index import RetrievalIndex, get_index

logger = logging.getLogger(__name__)

# RRF constant — standard value from Cormack et al., 2009
RRF_K: int = 60

# Retrieval top-k before RRF fusion (fetch more candidates, fuse, return top_k)
CANDIDATE_K: int = 20


# -----------------------------------------------------------------------
# Result type
# -----------------------------------------------------------------------

@dataclass
class SearchResult:
    chunk: Chunk
    score: float       # RRF fusion score (higher = better)
    rank: int          # 1-indexed rank in final fused list

    # Convenience accessors (delegate to chunk)
    @property
    def content(self) -> str:
        return self.chunk.content

    @property
    def filename(self) -> str:
        return self.chunk.filename

    @property
    def doc_title(self) -> str:
        return self.chunk.doc_title

    @property
    def section_header(self) -> str:
        return self.chunk.section_header

    @property
    def system_affected(self) -> str:
        return self.chunk.system_affected

    @property
    def resolution_status(self) -> str:
        return self.chunk.resolution_status

    @property
    def doc_type(self) -> str:
        return self.chunk.doc_type

    @property
    def last_updated_date(self) -> str:
        return self.chunk.last_updated_date


# -----------------------------------------------------------------------
# HybridRetriever
# -----------------------------------------------------------------------

class HybridRetriever:
    """Hybrid dense+sparse retriever with RRF fusion.

    Two named pipelines expose different retrieval strategies depending on
    the document shape and vocabulary characteristics of each tool.
    """

    def __init__(self, index: RetrievalIndex) -> None:
        self._index = index

    @property
    def model_name(self) -> str:
        """Name of the active embedding model (e.g. 'BAAI/bge-m3').

        Surfaced in the UI so a silent fallback (BGE-M3 → bge-small → TF-IDF →
        keyword) is visible rather than masquerading as the full retrieval stack.
        """
        return self._index.model_name

    # ------------------------------------------------------------------
    # Pipeline 1: search_process_docs — semantic-primary
    # ------------------------------------------------------------------

    def search_process_docs(
        self,
        query: str,
        top_k: int = 3,
        doc_type_filter: list[str] | None = None,
        recency_filter: str | None = None,
    ) -> list[SearchResult]:
        """Pure dense retrieval over HR process / policy docs.

        Dense only (sparse_weight=0.0). A/B testing showed
        sparse contribution actively hurts process MRR@5 — process queries are
        natural language and BGE-M3 dense handles semantic variation cleanly.

        Metadata filters (optional):
          doc_type_filter — restrict to specific doc_types (default: process + onboarding)
          recency_filter  — only return chunks with last_updated_date >= this value (YYYY-MM-DD)
        """
        where = _build_process_filter(doc_type_filter, recency_filter)
        return self._hybrid_retrieve(
            query=query,
            collection=self._index.process_collection,
            sparse_store=self._index.process_sparse,
            chunks=self._index.process_chunks,
            top_k=top_k,
            dense_weight=1.0,
            sparse_weight=0.0,
            where=where,
        )

    # ------------------------------------------------------------------
    # Pipeline 2: lookup_known_issues — BM25-heavy atomic records
    # ------------------------------------------------------------------

    def lookup_known_issues(
        self,
        query: str,
        top_k: int = 3,
        system_affected: str | None = None,
        resolution_status: str | None = None,
    ) -> list[SearchResult]:
        """BM25-heavy hybrid retrieval over ITSM incident ticket records.

        Sparse retrieval leads (70% weight in RRF). HR system vocabulary —
        PA30, EIB, RITM, SuccessFactors module names — is exact-match
        territory where BM25-style sparse scoring significantly outperforms
        dense alone (documented in eval/retrieval-smoke-notes.md).

        Metadata pre-filters (optional):
          system_affected    — e.g., "SuccessFactors_EC", "Workday_Integration"
          resolution_status  — e.g., "resolved", "open", "in_progress"
        """
        where = _build_ticket_filter(system_affected, resolution_status)
        return self._hybrid_retrieve(
            query=query,
            collection=self._index.ticket_collection,
            sparse_store=self._index.ticket_sparse,
            chunks=self._index.ticket_chunks,
            top_k=top_k,
            dense_weight=0.3,
            sparse_weight=0.7,
            where=where,
        )

    # ------------------------------------------------------------------
    # Internal: hybrid RRF pipeline
    # ------------------------------------------------------------------

    def _hybrid_retrieve(
        self,
        query: str,
        collection: Any,
        sparse_store: list[dict[str, float]],
        chunks: list[Chunk],
        top_k: int,
        dense_weight: float,
        sparse_weight: float,
        where: dict[str, Any] | None,
        rrf_k: int = RRF_K,
    ) -> list[SearchResult]:
        """Embed query, run dense + sparse retrieval, fuse with weighted RRF."""
        if collection.count() == 0:
            return []

        query_dense, query_sparse = self._index.embed_query(query)

        # Dense pass (ChromaDB)
        n_candidates = min(CANDIDATE_K, collection.count())
        dense_hits = self._index.query_dense(
            collection=collection,
            query_dense_vec=query_dense,
            n_results=n_candidates,
            where=where if where else None,
        )

        # Sparse pass (in-memory dot product)
        sparse_hits = self._index.query_sparse(
            sparse_store=sparse_store,
            query_lexical=query_sparse,
            n_results=n_candidates,
            where_filter=where,
            chunks=chunks,
        )

        # Weighted RRF fusion
        fused = _rrf_fuse(
            dense_hits=dense_hits,
            sparse_hits=sparse_hits,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            k=rrf_k,
        )

        results: list[SearchResult] = []
        for rank_0based, (chunk_idx, score) in enumerate(fused[:top_k]):
            if 0 <= chunk_idx < len(chunks):
                results.append(
                    SearchResult(
                        chunk=chunks[chunk_idx],
                        score=score,
                        rank=rank_0based + 1,
                    )
                )
        return results


# -----------------------------------------------------------------------
# Singleton retriever
# -----------------------------------------------------------------------

_RETRIEVER: HybridRetriever | None = None
_RETRIEVER_LOCK = __import__("threading").Lock()


def get_retriever() -> HybridRetriever:
    """Return the singleton HybridRetriever (builds index on first call)."""
    global _RETRIEVER
    if _RETRIEVER is None:
        with _RETRIEVER_LOCK:
            if _RETRIEVER is None:
                _RETRIEVER = HybridRetriever(get_index())
    return _RETRIEVER


def reset_retriever() -> None:
    """Reset the singleton — used in tests to inject a mock retriever."""
    global _RETRIEVER
    with _RETRIEVER_LOCK:
        _RETRIEVER = None


# -----------------------------------------------------------------------
# RRF implementation
# -----------------------------------------------------------------------

def _rrf_fuse(
    dense_hits: list[tuple[int, float]],
    sparse_hits: list[tuple[int, float]],
    dense_weight: float,
    sparse_weight: float,
    k: int = RRF_K,
) -> list[tuple[int, float]]:
    """Weighted Reciprocal Rank Fusion.

    Formula: rrf_score(doc) = Σ weight_list * 1 / (k + rank + 1)
    where rank is 0-indexed within each list.

    dense_hits: list of (chunk_idx, distance) — lower distance = better rank
    sparse_hits: list of (chunk_idx, score) — higher score = better rank

    Returns list of (chunk_idx, fused_score) sorted by score descending.
    """
    scores: dict[int, float] = {}

    # Dense list: sorted ascending by distance (already from ChromaDB)
    for rank, (chunk_idx, _dist) in enumerate(dense_hits):
        scores[chunk_idx] = scores.get(chunk_idx, 0.0) + dense_weight / (k + rank + 1)

    # Sparse list: sorted descending by score (already from query_sparse)
    for rank, (chunk_idx, _score) in enumerate(sparse_hits):
        scores[chunk_idx] = scores.get(chunk_idx, 0.0) + sparse_weight / (k + rank + 1)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# -----------------------------------------------------------------------
# Metadata filter builders
# -----------------------------------------------------------------------

def _build_process_filter(
    doc_type_filter: list[str] | None,
    recency_filter: str | None,
) -> dict[str, Any] | None:
    """Build ChromaDB where-clause for process doc queries."""
    conditions: list[dict[str, Any]] = []

    types = doc_type_filter or ["process", "onboarding"]
    if len(types) == 1:
        conditions.append({"doc_type": {"$eq": types[0]}})
    else:
        conditions.append({"doc_type": {"$in": types}})

    if recency_filter:
        conditions.append({"last_updated_date": {"$gte": recency_filter}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _build_ticket_filter(
    system_affected: str | None,
    resolution_status: str | None,
) -> dict[str, Any] | None:
    """Build ChromaDB where-clause for ticket record queries."""
    conditions: list[dict[str, Any]] = [{"doc_type": {"$eq": "known_issue"}}]

    if system_affected:
        conditions.append({"system_affected": {"$eq": system_affected}})
    if resolution_status:
        conditions.append({"resolution_status": {"$eq": resolution_status}})

    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}
