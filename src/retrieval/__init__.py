"""Retrieval layer — BGE-M3 hybrid+RRF retrieval for hr-ops-agent.

Public API:
    get_retriever()   → HybridRetriever (singleton, builds on first call)
    reset_retriever() → Reset singleton (test injection)
    HybridRetriever   → .search_process_docs() / .lookup_known_issues()
    SearchResult      → .content, .filename, .section_header, etc.
    Chunk             → raw chunk dataclass from chunker
    chunk_directory() → chunk all docs in a directory (used by index builder)
"""

from src.retrieval.chunker import Chunk, chunk_directory
from src.retrieval.index import RetrievalIndex, get_index, reset_index
from src.retrieval.retriever import HybridRetriever, SearchResult, get_retriever, reset_retriever

__all__ = [
    "Chunk",
    "chunk_directory",
    "RetrievalIndex",
    "get_index",
    "reset_index",
    "HybridRetriever",
    "SearchResult",
    "get_retriever",
    "reset_retriever",
]
