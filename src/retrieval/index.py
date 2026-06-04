"""Retrieval index: BGE-M3 embeddings + ChromaDB vector store.

Design decisions (see docs/hf-spaces-feasibility-spike.md):
  • BGE-M3 (BAAI/bge-m3): dense + sparse from one model, 8192-token window.
    Feasible on HF free-tier CPU (~570 MB, 16 GB RAM limit).
  • ChromaDB in-process: no server required; metadata-filtered retrieval.
  • Sparse vectors: BGE-M3 lexical_weights stored in a parallel in-memory
    list (ChromaDB metadata is JSON, not float-array-friendly for sparse).
  • Index persistence: persistent ChromaDB client at INDEX_DIR (configurable).
    Local dev: caches across restarts. HF Spaces: ephemeral — rebuilds on
    cold start (~30 s, acceptable for demo). Set REBUILD_INDEX=1 to force.

Fallback: if FlagEmbedding is not importable (CI, lightweight envs), the
module degrades gracefully — callers catch ImportError and fall back to
the naive keyword search in tools.py. The install gate is where
you confirm BGE-M3 actually loads in your target environment.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from src.retrieval.chunker import Chunk, chunk_directory

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------

DOCS_DIR = Path(__file__).parent.parent.parent / "synthetic-docs"
INDEX_DIR = Path(__file__).parent.parent.parent / "data" / "retrieval_index"

# BGE-M3 model — requires ~2.2 GB disk + ~570 MB RAM.
# Fallback chain (in order):
#   1. BGE-M3           (production: HF Spaces 50 GB storage — no constraint)
#   2. bge-small-en-v1.5  (~130 MB; local dev / CI with limited disk)
# Set BGE_M3_REQUIRED=1 to disable fallback and fail hard if BGE-M3 unavailable.
BGE_M3_MODEL_NAME = "BAAI/bge-m3"
BGE_SMALL_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# Collection names — two architectures
COLLECTION_PROCESS = "process_docs"
COLLECTION_TICKETS = "ticket_records"

# Instruction prefix for asymmetric retrieval (short query → long doc)
# BGE-M3 / E5 instruction-tuned: prepend to the QUERY side only
QUERY_INSTRUCTION = "Represent this HR query for retrieving relevant HR documents: "


# -----------------------------------------------------------------------
# RetrievalIndex singleton
# -----------------------------------------------------------------------

class RetrievalIndex:
    """Holds the ChromaDB client + BGE-M3 model + in-memory sparse vectors.

    Build by calling RetrievalIndex.build(). Access the singleton via
    get_index() — thread-safe, builds once on first call.
    """

    def __init__(
        self,
        chroma_client: Any,
        process_collection: Any,
        ticket_collection: Any,
        process_chunks: list[Chunk],
        ticket_chunks: list[Chunk],
        process_sparse: list[dict[str, float]],
        ticket_sparse: list[dict[str, float]],
        model: Any,
        model_name: str,
    ) -> None:
        self._chroma = chroma_client
        self.process_collection = process_collection
        self.ticket_collection = ticket_collection
        # Ordered parallel to collection insertion order
        self.process_chunks = process_chunks
        self.ticket_chunks = ticket_chunks
        # BGE-M3 lexical_weights per chunk (sparse vectors)
        self.process_sparse: list[dict[str, float]] = process_sparse
        self.ticket_sparse: list[dict[str, float]] = ticket_sparse
        self.model = model
        self.model_name = model_name
        # Serialises query-time model.encode() calls. run_agent_async dispatches
        # through a thread pool, so two concurrent sessions could otherwise call
        # encode() on the shared model simultaneously — not guaranteed safe for
        # torch CPU inference. Build-time embedding is single-threaded (startup),
        # so only the query path needs the guard.
        self._encode_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def query_dense(
        self,
        collection: Any,
        query_dense_vec: list[float],
        n_results: int,
        where: dict[str, Any] | None = None,
    ) -> list[tuple[int, float]]:
        """Dense retrieval from a ChromaDB collection.

        Returns list of (chunk_index, distance) sorted by distance ascending
        (lower = closer). ChromaDB uses L2 distance by default.
        """
        kwargs: dict[str, Any] = {
            "query_embeddings": [query_dense_vec],
            "n_results": min(n_results, collection.count()),
            "include": ["distances", "metadatas"],
        }
        if where:
            kwargs["where"] = where

        results = collection.query(**kwargs)
        ids = results["ids"][0]
        distances = results["distances"][0]

        hits: list[tuple[int, float]] = []
        for doc_id, dist in zip(ids, distances):
            chunk_idx = int(doc_id)
            hits.append((chunk_idx, float(dist)))
        return hits

    def query_sparse(
        self,
        sparse_store: list[dict[str, float]],
        query_lexical: dict[str, float],
        n_results: int,
        where_filter: dict[str, Any] | None,
        chunks: list[Chunk],
    ) -> list[tuple[int, float]]:
        """Sparse (lexical weight) retrieval via dot-product similarity.

        Filters by where_filter metadata before scoring (pre-filter, not post).
        Returns list of (chunk_index, score) sorted by score descending.
        """
        scores: list[tuple[int, float]] = []
        for idx, sparse_vec in enumerate(sparse_store):
            if where_filter and not _matches_filter(chunks[idx], where_filter):
                continue
            score = sum(
                query_lexical.get(tok, 0.0) * weight
                for tok, weight in sparse_vec.items()
            )
            if score > 0:
                scores.append((idx, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:n_results]

    def embed_query(self, query: str) -> tuple[list[float], dict[str, float]]:
        """Embed a query. Returns (dense_vec, sparse_vec).

        BGE-M3 path: dense uses instruction prefix (asymmetric retrieval — short
        query → long doc); sparse uses RAW query only. Chunk sparse vectors are
        computed on raw content (_embed_chunks), so the query sparse must match —
        prepending the instruction injects common tokens ("HR", "documents") that
        appear nowhere in chunk sparse vectors, producing systematic BM25 noise.
        Two encode calls: one instructed (dense), one raw (sparse).

        bge-small path: dense embedding + BM25-style sparse from single-token query.
        """
        # Serialise concurrent encode() — the shared model is not guaranteed
        # thread-safe under simultaneous query-time inference.
        with self._encode_lock:
            # Attempt BGE-M3 native (FlagEmbedding BGEM3FlagModel)
            try:
                # Raw query for both dense and sparse — BGE-M3 was not trained with
                # hand-written instruction prefixes (that is an E5/Instructor idiom).
                # Prepending QUERY_INSTRUCTION is off-distribution for BGE-M3 and
                # degrades dense ranking quality. Chunk vectors use raw content, so
                # query vectors must match.
                result = self.model.encode(
                    [query],
                    return_dense=True,
                    return_sparse=True,
                    return_colbert_vecs=False,
                )
                dense = result["dense_vecs"][0].tolist()
                sparse = _normalize_lexical(result["lexical_weights"][0])
                return dense, sparse
            except (AttributeError, TypeError):
                pass  # fall through to sentence-transformers path

            # sentence-transformers (bge-small fallback) — dense + BM25 query sparse
            dense = self.model.encode(
                QUERY_INSTRUCTION + query,
                normalize_embeddings=True,
            ).tolist()
        # Sparse: compute BM25-style query term weights (single-doc corpus = query itself)
        query_sparse_vecs = _bm25_sparse_vecs([query])
        sparse = query_sparse_vecs[0] if query_sparse_vecs else {}
        return dense, sparse

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def build(cls, docs_dir: Path = DOCS_DIR, index_dir: Path = INDEX_DIR) -> RetrievalIndex:
        """Build the index from scratch. Embeds all chunks and stores in ChromaDB."""
        import chromadb

        chunks = chunk_directory(docs_dir)
        process_chunks = [c for c in chunks if c.doc_type in ("process", "onboarding")]
        ticket_chunks = [c for c in chunks if c.doc_type == "known_issue"]

        logger.info(
            "Building retrieval index: %d process chunks, %d ticket chunks",
            len(process_chunks),
            len(ticket_chunks),
        )

        model, model_name = _load_model()

        # TF-IDF last-resort fallback: pre-fit on the UNION corpus so ticket
        # vectors don't inherit the process-only vocabulary from a lazy
        # first-batch fit. No-op for BGE-M3 / sentence-transformers.
        if isinstance(model, _TfidfModel):
            model.fit_corpus(
                [c.content for c in process_chunks]
                + [c.content for c in ticket_chunks]
            )

        # Embed all chunks
        logger.info("Embedding process docs...")
        proc_dense, proc_sparse = _embed_chunks(model, process_chunks, model_name)
        logger.info("Embedding ticket records...")
        tick_dense, tick_sparse = _embed_chunks(model, ticket_chunks, model_name)

        # Build ChromaDB collections
        index_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(index_dir))

        process_col = _build_collection(
            client, COLLECTION_PROCESS, process_chunks, proc_dense
        )
        ticket_col = _build_collection(
            client, COLLECTION_TICKETS, ticket_chunks, tick_dense
        )

        # Persist the corpus + model fingerprint so load_or_build can detect
        # drift and rebuild instead of silently reusing stale dense vectors.
        _write_fingerprint(docs_dir, index_dir, model_name)

        logger.info("Retrieval index built successfully (model: %s)", model_name)
        return cls(
            chroma_client=client,
            process_collection=process_col,
            ticket_collection=ticket_col,
            process_chunks=process_chunks,
            ticket_chunks=ticket_chunks,
            process_sparse=proc_sparse,
            ticket_sparse=tick_sparse,
            model=model,
            model_name=model_name,
        )

    @classmethod
    def load_or_build(cls, docs_dir: Path = DOCS_DIR, index_dir: Path = INDEX_DIR) -> RetrievalIndex:
        """Load existing index if present; rebuild if REBUILD_INDEX=1 or absent.

        Corpus-drift guard: _load re-chunks the docs and
        recomputes sparse vectors live but reuses the PERSISTED dense vectors.
        If the corpus changed since the index was built, those dense vectors are
        silently stale relative to the new chunks/sparse → wrong retrieval, no
        error. We compare a corpus fingerprint and rebuild on any mismatch (or
        when no fingerprint exists, e.g. an older index).
        """
        force_rebuild = os.environ.get("REBUILD_INDEX", "0") == "1"
        index_exists = (index_dir / "chroma.sqlite3").exists()

        if not force_rebuild and index_exists:
            if _read_fingerprint(index_dir).get("corpus") == _corpus_hash(docs_dir):
                logger.info("Loading existing retrieval index from %s", index_dir)
                try:
                    return cls._load(docs_dir, index_dir)
                except Exception:
                    logger.warning("Index load failed — rebuilding from scratch", exc_info=True)
            else:
                logger.warning(
                    "Corpus changed (or no fingerprint) since the index was built — "
                    "rebuilding to avoid stale dense vectors."
                )

        return cls.build(docs_dir, index_dir)

    @classmethod
    def _load(cls, docs_dir: Path, index_dir: Path) -> RetrievalIndex:
        """Load an existing ChromaDB index (avoids re-embedding on warm restart)."""
        import chromadb

        chunks = chunk_directory(docs_dir)
        process_chunks = [c for c in chunks if c.doc_type in ("process", "onboarding")]
        ticket_chunks = [c for c in chunks if c.doc_type == "known_issue"]

        model, model_name = _load_model()

        # Model-drift guard: a persisted collection has a fixed
        # embedding dimension. Loading it with a different model (e.g. a 512-dim
        # TF-IDF index against 1024-dim BGE-M3) crashes at query time. Detect the
        # model change up front and raise so load_or_build rebuilds cleanly.
        stored_model = _read_fingerprint(index_dir).get("model", "")
        if stored_model and stored_model != model_name:
            raise RuntimeError(
                f"Index was built with '{stored_model}' but '{model_name}' is now "
                f"active (model/dimension drift) — rebuild required."
            )

        client = chromadb.PersistentClient(path=str(index_dir))
        process_col = client.get_collection(COLLECTION_PROCESS)
        ticket_col = client.get_collection(COLLECTION_TICKETS)

        # Sparse vectors must be recomputed on load (not stored in ChromaDB)
        logger.info("Recomputing sparse vectors for warm load...")
        _, proc_sparse = _embed_chunks(model, process_chunks, model_name)
        _, tick_sparse = _embed_chunks(model, ticket_chunks, model_name)

        logger.info("Retrieval index loaded successfully (model: %s)", model_name)
        return cls(
            chroma_client=client,
            process_collection=process_col,
            ticket_collection=ticket_col,
            process_chunks=process_chunks,
            ticket_chunks=ticket_chunks,
            process_sparse=proc_sparse,
            ticket_sparse=tick_sparse,
            model=model,
            model_name=model_name,
        )


# -----------------------------------------------------------------------
# Singleton
# -----------------------------------------------------------------------

_INDEX: RetrievalIndex | None = None
_INDEX_LOCK = threading.Lock()


def get_index() -> RetrievalIndex:
    """Return the singleton RetrievalIndex, building it on first call."""
    global _INDEX
    if _INDEX is None:
        with _INDEX_LOCK:
            if _INDEX is None:
                _INDEX = RetrievalIndex.load_or_build()
    return _INDEX


def reset_index() -> None:
    """Reset the singleton — used in tests to inject a test index."""
    global _INDEX
    with _INDEX_LOCK:
        _INDEX = None


def peek_model_name() -> str | None:
    """Return the active model name if the index is already built, else None.

    Non-building: never triggers the ~30–100 s index build. Used by the UI to
    show retrieval status without forcing a cold-start build on page render.
    """
    return _INDEX.model_name if _INDEX is not None else None


# -----------------------------------------------------------------------
# Private helpers
# -----------------------------------------------------------------------

_FINGERPRINT_FILE = "corpus.fingerprint"


def _corpus_hash(docs_dir: Path) -> str:
    """SHA-256 over sorted (filename, content) of the chunked corpus.

    Mirrors chunk_directory's exclusion of provenance.md so a change to a
    non-chunked file does not force a needless rebuild.
    """
    import hashlib

    h = hashlib.sha256()
    for path in sorted(docs_dir.glob("*.md")):
        if path.name == "provenance.md":
            continue
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _write_fingerprint(docs_dir: Path, index_dir: Path, model_name: str) -> None:
    """Persist {corpus, model} alongside the index for drift detection."""
    import json

    payload = {"corpus": _corpus_hash(docs_dir), "model": model_name}
    try:
        (index_dir / _FINGERPRINT_FILE).write_text(
            json.dumps(payload), encoding="utf-8"
        )
    except OSError:
        logger.warning("Could not write corpus fingerprint", exc_info=True)


def _read_fingerprint(index_dir: Path) -> dict[str, str]:
    """Read the {corpus, model} fingerprint. Returns {} if absent/unreadable."""
    import json

    fp = index_dir / _FINGERPRINT_FILE
    if not fp.exists():
        return {}
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_model() -> tuple[Any, str]:
    """Load the embedding model.

    Fallback chain:
      1. BAAI/bge-m3 via FlagEmbedding  — production (HF Spaces).
         Requires ~2.2 GB disk. Provides dense + native sparse in one call.
      2. BAAI/bge-small-en-v1.5 via sentence-transformers  — local dev / CI.
         ~130 MB. Dense only; sparse handled by rank_bm25 (see _embed_chunks).

    Set BGE_M3_REQUIRED=1 to disable fallback and fail hard.
    """
    import shutil

    force_bge_m3 = os.environ.get("BGE_M3_REQUIRED", "0") == "1"

    # Attempt 1: BGE-M3 (FlagEmbedding) — only if disk space is sufficient.
    # BGE-M3 requires ~2.2 GB disk for model weights. Skip if insufficient.
    # Check against the HuggingFace cache drive (same as where model is stored).
    _hf_cache_drive = os.path.expanduser("~")
    _free_bytes = shutil.disk_usage(_hf_cache_drive).free
    _bge_m3_min_bytes = 2_400 * 1024 * 1024  # 2.4 GB with buffer

    if _free_bytes < _bge_m3_min_bytes and not force_bge_m3:
        logger.warning(
            "BGE-M3 skipped: only %.0f MB free, need >= 2400 MB for model weights. "
            "Falling back to bge-small-en-v1.5.",
            _free_bytes / 1024**2,
        )
    else:
        try:
            from FlagEmbedding import BGEM3FlagModel

            logger.info("Loading BGE-M3 model (CPU, use_fp16=False)...")
            model = BGEM3FlagModel(BGE_M3_MODEL_NAME, use_fp16=False, device="cpu")
            logger.info("BGE-M3 loaded successfully")
            return model, BGE_M3_MODEL_NAME
        except Exception as exc:
            if force_bge_m3:
                raise
            logger.warning("BGE-M3 unavailable (%s) — using bge-small-en-v1.5 fallback", exc)

    # Attempt 2: bge-small-en-v1.5 via sentence-transformers (~135 MB disk)
    _free_bytes_now = shutil.disk_usage(_hf_cache_drive).free
    _bge_small_min_bytes = 200 * 1024 * 1024  # 200 MB with buffer

    if _free_bytes_now < _bge_small_min_bytes:
        logger.warning(
            "bge-small-en-v1.5 skipped: only %.0f MB free, need >= 200 MB. "
            "Falling back to TF-IDF (no-download).",
            _free_bytes_now / 1024**2,
        )
    else:
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading bge-small-en-v1.5 (dense-only fallback)...")
            model = SentenceTransformer(BGE_SMALL_MODEL_NAME)
            logger.info(
                "bge-small-en-v1.5 loaded. Note: sparse vectors will use rank_bm25 "
                "(not BGE-M3 native sparse). For production deploy, ensure disk space "
                "for BGE-M3 (~2.2 GB) and set BGE_M3_REQUIRED=1."
            )
            return model, BGE_SMALL_MODEL_NAME
        except Exception as exc2:
            logger.warning(
                "bge-small-en-v1.5 unavailable (%s) — using scikit-learn TF-IDF fallback "
                "(no-download, no-GPU; sparse-primary retrieval, dense quality degraded)",
                exc2,
            )

    # Attempt 3: scikit-learn TF-IDF — no model download, no GPU.
    # Dense vectors = TF-IDF; sparse vectors = BM25 (rank_bm25).
    # Useful for disk-constrained CI or local dev without network.
    # WARN: retrieval quality is significantly lower than BGE-M3 (semantic queries won't match).
    # Set BGE_M3_REQUIRED=1 or BGEMODEL_REQUIRED=1 to fail instead of using this fallback.
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: F401

        logger.warning(
            "Using TF-IDF fallback for dense embeddings. "
            "Retrieval quality will be lexical-only. "
            "Suitable for harness validation / CI only. "
            "For production: install FlagEmbedding (BGE-M3) with sufficient disk space."
        )
        return _TfidfModel(), "tfidf-fallback"
    except ImportError as exc3:
        raise ImportError(
            "No embedding model available. Options:\n"
            "  1. FlagEmbedding (BGE-M3): uv add 'FlagEmbedding>=1.2.0'  (~2.2 GB disk)\n"
            "  2. sentence-transformers (bge-small): already installed but model download failed\n"
            "  3. scikit-learn (TF-IDF, no download): uv add scikit-learn\n"
        ) from exc3


class _TfidfModel:
    """Minimal TF-IDF 'model' that satisfies the sentence-transformers interface.

    Used as an absolute last fallback when no neural embedding model is available.
    Dense vectors are TF-IDF sparse-to-dense projections. Quality is much lower
    than BGE-M3 or bge-small — suitable for CI harness validation only.

    The vectorizer is fit lazily on the first batch of texts (the corpus). It is
    NOT refit on subsequent calls, so query encoding uses the corpus vocabulary.
    Unknown query tokens produce zero weights (harmless for cosine similarity).
    """

    def __init__(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer = TfidfVectorizer(
            max_features=512,    # 512-dim dense vectors
            sublinear_tf=True,
            strip_accents="unicode",
            analyzer="word",
            ngram_range=(1, 2),  # unigrams + bigrams
        )
        self._fitted = False

    def fit_corpus(self, texts: list[str]) -> None:
        """Fit the vectorizer on the FULL corpus up front.

        Without this, the lazy fit in encode() fits on whatever the first batch
        happens to be (process chunks), so ticket chunks embedded afterward are
        projected through the process-only vocabulary — degrading ticket
        retrieval. Fitting on the union of all chunk texts first makes every
        collection share one consistent vocabulary and dimension.
        """
        if texts:
            self._vectorizer.fit(texts)
            self._fitted = True

    def encode(self, texts: list[str] | str, normalize_embeddings: bool = True) -> Any:
        """Encode texts as TF-IDF dense vectors (512-dim).

        Accepts a single string or a list of strings.
        Returns a 1D array for a single string, 2D for a list.
        """
        import numpy as np

        single = isinstance(texts, str)
        if isinstance(texts, str):
            texts_list: list[str] = [texts]
        else:
            texts_list = list(texts)

        if not self._fitted:
            self._vectorizer.fit(texts_list)
            self._fitted = True

        matrix = self._vectorizer.transform(texts_list).toarray()
        if normalize_embeddings:
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            matrix = matrix / norms

        return matrix[0] if single else matrix


def _embed_chunks(
    model: Any,
    chunks: list[Chunk],
    model_name: str = "",
) -> tuple[list[list[float]], list[dict[str, float]]]:
    """Embed a list of chunks. Returns (dense_vecs, sparse_vecs).

    Dense:  model embeddings (BGE-M3 or bge-small via sentence-transformers)
    Sparse: BGE-M3 native lexical_weights  OR  rank_bm25 term weights (fallback)
    """
    if not chunks:
        return [], []

    texts = [c.content for c in chunks]

    # Try BGE-M3 native (FlagEmbedding BGEM3FlagModel)
    try:
        results = model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
            batch_size=8,
        )
        dense_vecs: list[list[float]] = [v.tolist() for v in results["dense_vecs"]]
        sparse_vecs: list[dict[str, float]] = [
            _normalize_lexical(lw) for lw in results["lexical_weights"]
        ]
        return dense_vecs, sparse_vecs
    except (AttributeError, TypeError):
        pass  # sentence-transformers model — fall through to BM25 sparse

    # sentence-transformers / TF-IDF fallback — dense via model.encode, sparse via BM25
    vecs = model.encode(texts, normalize_embeddings=True)
    # vecs may be ndarray (sentence-transformers) or ndarray (TF-IDF _TfidfModel)
    import numpy as np  # noqa: PLC0415

    if not isinstance(vecs, np.ndarray):
        vecs = np.array(vecs)
    dense_vecs = [v.tolist() for v in vecs]
    sparse_vecs = _bm25_sparse_vecs(texts)
    return dense_vecs, sparse_vecs


def _bm25_sparse_vecs(texts: list[str]) -> list[dict[str, float]]:
    """Build BM25-style sparse term weight vectors for a corpus.

    Returns a list of {token: bm25_score} dicts, one per document.
    Each doc is treated as a one-doc query against the full corpus —
    the BM25 score of document d against itself is the sum of BM25 term
    weights for each unique token in d.

    Used in the same sparse dot-product scoring path as BGE-M3 lexical_weights.
    This is the local dev / CI fallback; BGE-M3 native sparse is used in production.
    """
    import re

    stopwords = frozenset({
        "the", "a", "an", "in", "is", "are", "of", "to", "for", "and",
        "or", "at", "by", "on", "with", "this", "that", "it", "be",
        "was", "as", "from", "not", "but", "have", "has", "been",
    })

    def tokenize(text: str) -> list[str]:
        return [
            t for t in re.findall(r"\b[a-zA-Z0-9_\-]+\b", text.lower())
            if t not in stopwords
        ]

    tokenized = [tokenize(t) for t in texts]

    try:
        from rank_bm25 import BM25Okapi

        bm25 = BM25Okapi(tokenized)
        sparse: list[dict[str, float]] = []
        for idx, doc_tokens in enumerate(tokenized):
            unique_tokens = list(set(doc_tokens))
            if not unique_tokens:
                sparse.append({})
                continue
            # Score this document against each unique token as a 1-token query
            token_weights: dict[str, float] = {}
            for tok in unique_tokens:
                scores = bm25.get_scores([tok])
                token_weights[tok] = max(0.0, float(scores[idx]))
            # Normalize by max weight so scores are in [0, 1]
            max_w = max(token_weights.values(), default=1.0)
            if max_w > 0:
                token_weights = {k: v / max_w for k, v in token_weights.items() if v > 0}
            sparse.append(token_weights)
        return sparse
    except ImportError:
        logger.warning("rank_bm25 not available — using simple TF sparse vectors")
        # Ultra-simple fallback: normalized term frequency
        result: list[dict[str, float]] = []
        for doc_tokens in tokenized:
            from collections import Counter
            counts = Counter(doc_tokens)
            total = max(len(doc_tokens), 1)
            result.append({tok: cnt / total for tok, cnt in counts.items()})
        return result


def _normalize_lexical(lexical_weights: Any) -> dict[str, float]:
    """Convert BGEM3FlagModel lexical_weights output to {token_str: weight} dict.

    BGE-M3 returns lexical_weights as a dict keyed by token ids (int) — the
    model's tokenizer maps ids back to strings. We store them as-is with
    str-cast keys so the sparse scoring loop can work without the tokenizer.
    """
    if isinstance(lexical_weights, dict):
        return {str(k): float(v) for k, v in lexical_weights.items() if float(v) > 0}
    # Some versions return a list of (token_id, weight) pairs
    return {str(k): float(v) for k, v in lexical_weights if float(v) > 0}


def _build_collection(
    client: Any,
    name: str,
    chunks: list[Chunk],
    dense_vecs: list[list[float]],
) -> Any:
    """Create or recreate a ChromaDB collection and insert chunks."""
    try:
        client.delete_collection(name)
    except Exception:
        pass  # Collection didn't exist yet

    collection = client.create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )

    if not chunks:
        return collection

    ids = [str(i) for i in range(len(chunks))]
    metadatas = [_chunk_to_metadata(c) for c in chunks]
    documents = [c.content for c in chunks]

    collection.add(
        ids=ids,
        embeddings=dense_vecs,
        metadatas=metadatas,
        documents=documents,
    )
    return collection


def _chunk_to_metadata(chunk: Chunk) -> dict[str, str]:
    """Convert a Chunk to a ChromaDB-compatible metadata dict (str values only)."""
    return {
        "doc_title": chunk.doc_title,
        "doc_type": chunk.doc_type,
        "filename": chunk.filename,
        "last_updated_date": chunk.last_updated_date,
        "section_header": chunk.section_header,
        "system_affected": chunk.system_affected,
        "resolution_status": chunk.resolution_status,
    }


def _matches_filter(chunk: Chunk, where_filter: dict[str, Any]) -> bool:
    """Check if a chunk satisfies a metadata filter dict.

    Supports two forms:
      {"field": "value"}                   → exact match
      {"field": {"$in": ["a", "b"]}}       → membership
      {"$and": [{...}, {...}]}             → logical AND
    """
    if "$and" in where_filter:
        return all(_matches_filter(chunk, sub) for sub in where_filter["$and"])

    meta = _chunk_to_metadata(chunk)
    for key, condition in where_filter.items():
        if key.startswith("$"):
            continue
        actual = meta.get(key, "")
        if isinstance(condition, dict):
            op = next(iter(condition))
            val = condition[op]
            if op == "$in":
                if actual not in val:
                    return False
            elif op == "$eq":
                if actual != val:
                    return False
            elif op == "$ne":
                if actual == val:
                    return False
        else:
            if actual != condition:
                return False
    return True
