"""Tests for the RRF fusion logic and HybridRetriever wiring.

Model-free: uses mock index so no BGE-M3 or ChromaDB required.
The retrieval layer's core correctness — RRF math, architecture separation,
metadata filter pass-through — is testable without any embedding model.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.retrieval.chunker import Chunk
from src.retrieval.retriever import (
    HybridRetriever,
    SearchResult,
    _build_process_filter,
    _build_ticket_filter,
    _rrf_fuse,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(
    idx: int,
    doc_type: str = "process",
    system_affected: str = "",
    resolution_status: str = "",
    filename: str = "doc.md",
) -> Chunk:
    return Chunk(
        chunk_id=f"{filename}::{idx}",
        doc_title="Test Doc",
        doc_type=doc_type,  # type: ignore[arg-type]
        filename=filename,
        last_updated_date="2026-01-01",
        section_header="Section",
        content=f"Content for chunk {idx}",
        system_affected=system_affected,
        resolution_status=resolution_status,
    )


def _make_mock_index(
    process_chunks: list[Chunk],
    ticket_chunks: list[Chunk],
    dense_hits: list[tuple[int, float]] | None = None,
    sparse_hits: list[tuple[int, float]] | None = None,
) -> MagicMock:
    """Build a minimal mock RetrievalIndex for HybridRetriever tests."""
    index = MagicMock()
    index.process_chunks = process_chunks
    index.ticket_chunks = ticket_chunks
    index.process_sparse = [{} for _ in process_chunks]
    index.ticket_sparse = [{} for _ in ticket_chunks]

    # embed_query → dummy (dense_vec, sparse_vec)
    index.embed_query.return_value = ([0.1] * 8, {"pa30": 0.9, "eib": 0.8})

    # query_dense → provided hits or default
    _dense = dense_hits if dense_hits is not None else [(0, 0.1), (1, 0.3)]
    index.query_dense.return_value = _dense

    # query_sparse → provided hits or default
    _sparse = sparse_hits if sparse_hits is not None else [(1, 0.9), (0, 0.5)]
    index.query_sparse.return_value = _sparse

    # process_collection and ticket_collection
    for col_name in ("process_collection", "ticket_collection"):
        col = MagicMock()
        col.count.return_value = max(len(process_chunks), 1)
        setattr(index, col_name, col)

    return index


# ---------------------------------------------------------------------------
# _rrf_fuse
# ---------------------------------------------------------------------------

class TestRrfFuse:
    def test_higher_ranked_in_both_lists_wins(self) -> None:
        # chunk 0 ranks first in both lists → highest fused score
        dense = [(0, 0.1), (1, 0.2), (2, 0.3)]
        sparse = [(0, 1.0), (1, 0.5), (2, 0.2)]
        result = _rrf_fuse(dense, sparse, dense_weight=0.5, sparse_weight=0.5, k=60)
        assert result[0][0] == 0  # chunk 0 is top

    def test_sparse_heavy_weights_favour_sparse_rank(self) -> None:
        # chunk 0 ranks #1 dense, chunk 1 ranks #1 sparse
        # with dense_weight=0.1, sparse_weight=0.9 → chunk 1 should win
        dense = [(0, 0.1), (1, 0.3)]   # 0 is better dense
        sparse = [(1, 1.0), (0, 0.5)]  # 1 is better sparse
        result = _rrf_fuse(dense, sparse, dense_weight=0.1, sparse_weight=0.9, k=60)
        assert result[0][0] == 1  # sparse winner wins overall

    def test_dense_heavy_weights_favour_dense_rank(self) -> None:
        dense = [(0, 0.1), (1, 0.3)]
        sparse = [(1, 1.0), (0, 0.5)]
        result = _rrf_fuse(dense, sparse, dense_weight=0.9, sparse_weight=0.1, k=60)
        assert result[0][0] == 0  # dense winner wins overall

    def test_scores_are_positive(self) -> None:
        dense = [(0, 0.5)]
        sparse = [(0, 0.8)]
        result = _rrf_fuse(dense, sparse, dense_weight=0.5, sparse_weight=0.5, k=60)
        assert result[0][1] > 0

    def test_empty_dense_list(self) -> None:
        sparse = [(0, 1.0), (1, 0.5)]
        result = _rrf_fuse([], sparse, dense_weight=0.5, sparse_weight=0.5, k=60)
        assert len(result) == 2
        assert result[0][0] == 0  # rank 1 in sparse

    def test_empty_sparse_list(self) -> None:
        dense = [(0, 0.1), (1, 0.2)]
        result = _rrf_fuse(dense, [], dense_weight=0.5, sparse_weight=0.5, k=60)
        assert len(result) == 2
        assert result[0][0] == 0  # rank 1 in dense

    def test_both_empty(self) -> None:
        result = _rrf_fuse([], [], dense_weight=0.5, sparse_weight=0.5, k=60)
        assert result == []

    def test_chunk_in_only_one_list_still_gets_score(self) -> None:
        dense = [(0, 0.5)]
        sparse = [(1, 0.9)]  # chunk 1 only in sparse
        result = _rrf_fuse(dense, sparse, dense_weight=0.5, sparse_weight=0.5, k=60)
        chunk_ids = [r[0] for r in result]
        assert 0 in chunk_ids
        assert 1 in chunk_ids

    def test_rrf_formula_exact_value(self) -> None:
        # dense_weight=1.0, k=60, rank=0 → score = 1.0 / (60 + 0 + 1) = 1/61
        dense = [(42, 0.1)]
        result = _rrf_fuse(dense, [], dense_weight=1.0, sparse_weight=0.0, k=60)
        expected = 1.0 / 61
        assert abs(result[0][1] - expected) < 1e-9


# ---------------------------------------------------------------------------
# Metadata filter builders
# ---------------------------------------------------------------------------

class TestBuildProcessFilter:
    def test_default_returns_process_and_onboarding(self) -> None:
        f = _build_process_filter(None, None)
        assert f is not None
        # Should include {"$in": ["process", "onboarding"]}
        assert "process" in str(f)
        assert "onboarding" in str(f)

    def test_single_type_uses_eq(self) -> None:
        f = _build_process_filter(["process"], None)
        assert "$eq" in str(f)

    def test_recency_filter_included(self) -> None:
        f = _build_process_filter(None, "2026-01-01")
        assert "last_updated_date" in str(f)
        assert "2026-01-01" in str(f)

    def test_no_filter_returns_none_not_empty_dict(self) -> None:
        # recency_filter=None, doc_type_filter default → non-None (has type filter)
        f = _build_process_filter(None, None)
        assert f is not None  # always has a doc_type constraint


class TestBuildTicketFilter:
    def test_base_filter_is_known_issue(self) -> None:
        f = _build_ticket_filter(None, None)
        assert f is not None
        assert "known_issue" in str(f)

    def test_system_affected_added(self) -> None:
        f = _build_ticket_filter("SuccessFactors_EC", None)
        assert "SuccessFactors_EC" in str(f)

    def test_resolution_status_added(self) -> None:
        f = _build_ticket_filter(None, "resolved")
        assert "resolved" in str(f)

    def test_both_filters_combined(self) -> None:
        f = _build_ticket_filter("Workday_Integration", "open")
        assert "Workday_Integration" in str(f)
        assert "open" in str(f)


# ---------------------------------------------------------------------------
# HybridRetriever pipeline routing
# ---------------------------------------------------------------------------

class TestHybridRetrieverPipelines:
    def _make_retriever(
        self,
        n_process: int = 3,
        n_tickets: int = 3,
    ) -> HybridRetriever:
        process_chunks = [_make_chunk(i, doc_type="process") for i in range(n_process)]
        ticket_chunks = [
            _make_chunk(i, doc_type="known_issue", system_affected="Workday_Integration")
            for i in range(n_tickets)
        ]
        index = _make_mock_index(process_chunks, ticket_chunks)
        return HybridRetriever(index)

    def test_search_process_docs_returns_search_results(self) -> None:
        r = self._make_retriever()
        results = r.search_process_docs("how to request time off", top_k=2)
        assert isinstance(results, list)
        assert all(isinstance(x, SearchResult) for x in results)

    def test_search_process_docs_respects_top_k(self) -> None:
        r = self._make_retriever(n_process=5)
        results = r.search_process_docs("time off", top_k=2)
        assert len(results) <= 2

    def test_lookup_known_issues_returns_search_results(self) -> None:
        r = self._make_retriever()
        results = r.lookup_known_issues("PA30 locked error", top_k=2)
        assert isinstance(results, list)
        assert all(isinstance(x, SearchResult) for x in results)

    def test_search_process_uses_process_collection(self) -> None:
        r = self._make_retriever()
        r._index.query_dense.return_value = [(0, 0.1)]
        r._index.query_sparse.return_value = [(0, 0.9)]
        r.search_process_docs("test")
        # Should have used process_collection
        call_args = r._index.query_dense.call_args
        assert call_args[1]["collection"] is r._index.process_collection

    def test_lookup_uses_ticket_collection(self) -> None:
        r = self._make_retriever()
        r._index.query_dense.return_value = [(0, 0.1)]
        r._index.query_sparse.return_value = [(0, 0.9)]
        r.lookup_known_issues("EIB error")
        call_args = r._index.query_dense.call_args
        assert call_args[1]["collection"] is r._index.ticket_collection

    def test_process_pipeline_dense_weight_greater(self) -> None:
        """search_process_docs uses 70/30 — verify RRF behaviour is semantic-primary.

        When chunk 0 leads in dense, chunk 1 leads in sparse, semantic pipeline
        should prefer chunk 0 (dense weight 0.7 > 0.3).
        """
        process_chunks = [_make_chunk(i, doc_type="process") for i in range(2)]
        ticket_chunks: list[Chunk] = []
        index = _make_mock_index(
            process_chunks,
            ticket_chunks,
            dense_hits=[(0, 0.1), (1, 0.9)],   # chunk 0 wins dense
            sparse_hits=[(1, 1.0), (0, 0.2)],  # chunk 1 wins sparse
        )
        r = HybridRetriever(index)
        results = r.search_process_docs("query", top_k=2)
        assert results[0].chunk.chunk_id == process_chunks[0].chunk_id

    def test_ticket_pipeline_sparse_weight_greater(self) -> None:
        """lookup_known_issues uses 30/70 — verify RRF behaviour is BM25-heavy.

        When chunk 0 leads in dense, chunk 1 leads in sparse, BM25-heavy pipeline
        should prefer chunk 1 (sparse weight 0.7 > 0.3).
        """
        process_chunks: list[Chunk] = []
        ticket_chunks = [_make_chunk(i, doc_type="known_issue") for i in range(2)]
        index = _make_mock_index(
            process_chunks,
            ticket_chunks,
            dense_hits=[(0, 0.1), (1, 0.9)],   # chunk 0 wins dense
            sparse_hits=[(1, 1.0), (0, 0.2)],  # chunk 1 wins sparse
        )
        r = HybridRetriever(index)
        results = r.lookup_known_issues("RITM routing error", top_k=2)
        assert results[0].chunk.chunk_id == ticket_chunks[1].chunk_id

    def test_empty_collection_returns_empty_list(self) -> None:
        r = self._make_retriever()
        r._index.process_collection.count.return_value = 0
        results = r.search_process_docs("query")
        assert results == []

    def test_search_result_properties(self) -> None:
        r = self._make_retriever()
        r._index.query_dense.return_value = [(0, 0.1)]
        r._index.query_sparse.return_value = [(0, 0.9)]
        results = r.search_process_docs("query", top_k=1)
        assert len(results) == 1
        sr = results[0]
        assert sr.rank == 1
        assert sr.score > 0
        assert sr.content
        assert sr.filename
