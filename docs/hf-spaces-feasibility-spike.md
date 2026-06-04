# HF Spaces Free-Tier Feasibility Spike — v0.1

**Date:** 2025-12 | **Status:** PASS (walking skeleton)

Confirms that the walking skeleton (v0.1, no vector retrieval) can deploy on HF Spaces
free tier. Also documents the future-retrieval risk (BGE-M3 + ChromaDB) and chosen fallback.

---

## v0.1 (this deploy — naive lookup, no vector index)

| Resource | Requirement | Free tier limit | Status |
|---|---|---|---|
| Python runtime | 3.11 | ✅ Supported | PASS |
| Streamlit UI | ~50 lines | ✅ Streamlit SDK runtime | PASS |
| FastAPI backend | ≤512MB RAM at idle | ✅ 16GB RAM free tier | PASS |
| Disk (code + docs) | ~2MB | ✅ 50GB storage | PASS |
| No GPU required | CPU-only | ✅ Free tier is CPU | PASS |
| API key | ANTHROPIC_API_KEY as HF Secret | ✅ HF Space secrets support | PASS |

**Verdict:** v0.1 walking skeleton deploys on HF Spaces free tier with no constraints.

**Deploy command:** `huggingface-hub` CLI or GitHub Actions push to HF Space repo.

---

## Future retrieval risk (BGE-M3 + ChromaDB)

| Risk | Assessment |
|---|---|
| BGE-M3 model size | ~570MB — fits within 16GB RAM free tier |
| ChromaDB | In-process, no server required — fine |
| Embedding index for the scaled corpus (≥40 docs / ~150 chunks) | ~2–5MB serialized — negligible |
| Cold start time (model load) | ~15–30s on free tier CPU — acceptable for demo |
| Persistent storage for vector index | HF Spaces has ephemeral storage unless using Datasets — index must rebuild on startup or be committed |

**Risk: index rebuild on cold start.** HF Spaces free tier has no persistent disk between
restarts. Options:
1. ✅ Commit the pre-built ChromaDB index to the Space repo (<5MB) — rebuilds only on redeploy
2. ✅ Build index at startup from committed `synthetic-docs/` — ~30s cold start, acceptable for demo
3. Use HF Datasets as persistent storage — adds complexity, not needed at this scale

**Chosen fallback:** Option 2 — build from docs at startup. If cold start >60s,
switch to Option 1 (commit the index). No paid tier required.

---

## Install Gate Result (2026-06-03)

| Target | Status | Notes |
|---|---|---|
| HF Spaces free tier | **PASS** | 50 GB storage >> 2.2 GB BGE-M3 weight files; 16 GB RAM >> 570 MB loaded model |
| Local dev (C: drive) | **BLOCKED** | C: drive 340 MB free < 2.2 GB required for BGE-M3 model weights |

**Local dev fallback active:** `BAAI/bge-small-en-v1.5` (~130 MB) + `rank_bm25` (pure Python).
Set `BGE_M3_REQUIRED=1` to disable fallback and require BGE-M3.

**Architecture is unchanged by fallback:** ChromaDB + RRF + two-pipeline design applies
to both BGE-M3 (dense+sparse native) and bge-small (dense+BM25 sparse). The fallback
is transparent to `tools.py` — `search_process_docs` / `lookup_known_issues` call
`get_retriever()` regardless of which model backs it.

---

## v0.3 public-safe deploy

The committed line is: public deploy after the security-hardening slice. Until then,
the Space is private/unlisted. HF supports private/unlisted Spaces on free tier.

**Action for v0.1:** Deploy as private/unlisted. Share URL for review only. Make public after the security-hardening slice.

---

## Deploy checklist (v0.1)

- [ ] Create HF Space: `huggingface-cli repo create hr-ops-agent --type space --space_sdk streamlit`
- [ ] Add `ANTHROPIC_API_KEY` as HF Space secret
- [ ] Add `API_URL=http://localhost:8000` → Note: Streamlit and FastAPI must run in the same process on HF Spaces, or use `subprocess` to start uvicorn. **Decision: for v0.1, combine into single entry point or call orchestrator directly from app.py.**
- [ ] Push to HF Space: `git push huggingface main`
- [ ] Verify Space starts, agent responds to a test query
- [ ] Set Space to private/unlisted until the security slice ships

**Entry point note (v0.1):** HF Spaces runs `streamlit run app.py`. The Streamlit app
currently calls the FastAPI endpoint. For a simple v0.1 deploy, refactor `app.py` to call
the orchestrator directly (skip FastAPI) — reduces infrastructure complexity for the demo.
FastAPI is still tested and present in the codebase; the UI just imports orchestrator
directly for the HF deploy. This is a deployment decision, not an architectural change.
