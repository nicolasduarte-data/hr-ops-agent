# HR Ops Agent — Architecture Reference

## Retrieval Layer Design Decisions

### Vector Store: ChromaDB

**Choice:** ChromaDB (in-process, persistent client)

**Rationale:**
- **No server required.** ChromaDB runs in-process — no separate container, no network hop, no infra for a demo corpus.
- **Metadata filtering.** Natively supports structured `where` filters on metadata (`doc_type`, `system_affected`, `resolution_status`). This is non-negotiable for the two-architecture design: `lookup_known_issues` pre-filters by `system_affected` before scoring.
- **HF Spaces compatible.** Runs on the free-tier CPU runtime with no changes. Persistent client writes to a local path; ephemeral on HF Spaces means the index rebuilds on cold start (~30s), which is acceptable for a demo.
- **50 GB storage available on HF free tier** — the serialized ChromaDB index for ~150 chunks is < 5 MB.

**Alternatives considered:**

| Store | Why not chosen |
|---|---|
| FAISS | No metadata filtering without external filter layer; more manual index management |
| LanceDB | Persistent, metadata-capable, but adds a new dependency with less community documentation than ChromaDB |
| Pinecone / Weaviate | Cloud-hosted; not compatible with offline demo or HF free tier |

---

### Embedding Model: BGE-M3 / bge-small-en-v1.5 fallback

**Production target:** `BAAI/bge-m3`
- Dense + sparse (lexical_weights) + late-interaction from one model
- 8192-token context window (handles full ticket records without truncation)
- ~570 MB RAM, ~2.2 GB disk for model weights
- HF free tier: 16 GB RAM + 50 GB storage → **PASS**

**Local dev / CI fallback:** `BAAI/bge-small-en-v1.5`
- Dense only (~130 MB disk, ~100 MB RAM)
- Sparse via `rank_bm25` (pure Python, no download)
- Used when BGE-M3 cannot be downloaded (e.g., limited disk space)
- Set `BGE_M3_REQUIRED=1` to disable fallback and fail hard

**Install gate result:**
- HF Spaces: PASS (50 GB disk, no constraint)
- Local machine: BLOCKED (C: drive 340 MB free < 2.2 GB required)

---

### Two Retrieval Architectures

The two tools use distinct retrieval strategies because their document shapes have
fundamentally different vocabulary characteristics.

#### `search_process_docs` — Semantic-primary

- **Weighting:** 70% dense, 30% sparse in RRF
- **Collection:** `process_docs` — policy/process/onboarding docs
- **Metadata filters:** `doc_type in ["process", "onboarding"]`; optional `last_updated_date >= X`
- **Why dense-first:** HR policy docs use natural language with high semantic variation.
  "How to take vacation days" → "PTO (Vacation) — Time Off Requests". Zero lexical overlap,
  high semantic match. Dense embeddings handle this. Sparse contributes for system names
  (Workday, SuccessFactors) that appear verbatim in both query and doc.

#### `lookup_known_issues` — BM25-heavy atomic records

- **Weighting:** 30% dense, 70% sparse in RRF
- **Collection:** `ticket_records` — ITSM incident records (one per file, atomic units)
- **Metadata filters:** `doc_type == "known_issue"`; optional `system_affected`, `resolution_status`
- **Why sparse-first:** HR system vocabulary is controlled and exact: PA30, EIB, RITM,
  INC/CHG, SuccessFactors_EC, Workday_Integration, SAP_Concur. Dense models conflate
  acronyms across semantic neighbours (EIB → "bank" → wrong). BM25-style sparse scoring
  rewards exact token matches — the correct behaviour for system-specific incident lookup.
  Three failure cases are documented in `eval/retrieval-smoke-notes.md` (PA30, EIB
  supervisory org, RITM routing) that were confirmed misses under dense-only retrieval.

---

### Hybrid RRF Fusion

**Formula (Cormack et al., 2009):**
```
rrf_score(doc) = Σᵢ weight_i / (k + rank_i + 1)
```

- `k = 60` (standard value; prevents dominance by rank-1 documents)
- Dense list: sorted ascending by cosine distance (ChromaDB output)
- Sparse list: sorted descending by dot-product score
- Results merged and sorted by fused score descending

**Why RRF over score normalisation:**
RRF is rank-based — it doesn't require score distributions to be comparable between
dense and sparse lists. Normalising cosine distances and BM25 scores onto a common
scale requires calibration that is corpus-specific. RRF avoids this entirely.

---

### Index Lifecycle

**Build:** On first call to `get_index()` (singleton, double-checked lock).
All chunks embedded; dense vectors stored in ChromaDB; sparse vectors (BM25/BGE-M3)
kept in memory alongside. Total build time: ~30s on CPU for 150 chunks.

**Persistence:** ChromaDB persists to `data/retrieval_index/` (gitignored).
Warm restart loads dense from ChromaDB and recomputes sparse from docs.
HF Spaces: ephemeral storage → index rebuilds on each cold start (~30s).

**Force rebuild:** `REBUILD_INDEX=1` environment variable.

---

### Data Flow

```
synthetic-docs/*.md
        │
        ▼  chunker.py (paragraph-group + atomic ITSM chunks)
    ~150 Chunk objects (with doc_title / section_header / system_affected / etc.)
        │
        ▼  index.py (BGE-M3 or bge-small)
    Dense vectors → ChromaDB (process_docs + ticket_records collections)
    Sparse vectors → in-memory list (parallel to ChromaDB insertion order)
        │
        ▼  retriever.py (HybridRetriever)
    Query → embed_query → (dense_vec, sparse_vec)
    Dense pass:  ChromaDB.query + metadata filter
    Sparse pass: dot-product against in-memory sparse store
    RRF fusion → ranked SearchResult list
        │
        ▼  tools.py (search_process_docs / lookup_known_issues)
    top-1 result → excerpt + metadata → Claude tool_result
```
