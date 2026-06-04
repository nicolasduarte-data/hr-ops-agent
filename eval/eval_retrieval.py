#!/usr/bin/env python3
"""Retrieval metrics evaluation harness.

Computes recall@3, MRR@5, NDCG@5, and RAGAS-style context precision/recall
for the hybrid retrieval pipeline against the gold set.

Two pipelines are evaluated separately:
  - process   → search_process_docs (semantic-primary hybrid)
  - ticket    → lookup_known_issues (BM25-heavy hybrid)

Outputs are appended to eval/REPORT.md under a "Retrieval Metrics" section
and printed to stdout.

Usage:
    uv run python eval/eval_retrieval.py [--gold eval/retrieval-gold/gold_set.jsonl]
                                         [--top-k 5]
                                         [--pipeline process|ticket|both]
                                         [--report]          # appends to REPORT.md
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

GOLD_FILE = Path(__file__).parent / "retrieval-gold" / "gold_set.jsonl"
REPORT_FILE = Path(__file__).parent / "REPORT.md"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    """Recall@k = |retrieved[:k] ∩ relevant| / |relevant|"""
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    rel_set = set(relevant)
    return len(top_k & rel_set) / len(rel_set)


def reciprocal_rank(retrieved: list[str], relevant: list[str]) -> float:
    """MRR contribution: 1/rank of first relevant item (0 if none found)."""
    rel_set = set(relevant)
    for i, doc in enumerate(retrieved):
        if doc in rel_set:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    """NDCG@k with binary relevance (rel=1 if in relevant set, else 0)."""
    rel_set = set(relevant)

    def dcg(docs: list[str]) -> float:
        return sum(
            1.0 / math.log2(i + 2)
            for i, doc in enumerate(docs[:k])
            if doc in rel_set
        )

    actual_dcg = dcg(retrieved)
    # Ideal DCG: top min(|relevant|, k) positions all relevant
    n_ideal = min(len(rel_set), k)
    ideal_dcg = sum(1.0 / math.log2(i + 2) for i in range(n_ideal))

    if ideal_dcg == 0:
        return 0.0
    return actual_dcg / ideal_dcg


def context_precision(retrieved: list[str], relevant: list[str], k: int) -> float:
    """RAGAS-style context precision@k: fraction of top-k results that are relevant.

    (Retrieval-side only — does not evaluate generation quality.)
    """
    if not retrieved:
        return 0.0
    top_k = retrieved[:k]
    rel_set = set(relevant)
    return sum(1 for doc in top_k if doc in rel_set) / len(top_k)


def context_recall(retrieved: list[str], relevant: list[str], k: int) -> float:
    """RAGAS-style context recall@k: fraction of relevant docs found in top-k."""
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    rel_set = set(relevant)
    return len(top_k & rel_set) / len(rel_set)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def _dedup_filenames(results: list[Any]) -> list[str]:
    """Return ranked unique filenames from retrieval results.

    Multiple chunks from the same file may be returned; the gold set is
    file-level, so we deduplicate to avoid inflating recall/NDCG.
    First occurrence (highest-ranked) wins.
    """
    seen: set[str] = set()
    ranked: list[str] = []
    for r in results:
        fn = r.filename
        if fn not in seen:
            seen.add(fn)
            ranked.append(fn)
    return ranked


def retrieve_process(query: str, top_k: int) -> list[str]:
    """Run search_process_docs and return ranked unique filenames."""
    from src.retrieval.retriever import get_retriever
    retriever = get_retriever()
    # Fetch more candidates than top_k to allow deduplication while still returning top_k unique
    results = retriever.search_process_docs(query, top_k=top_k * 3)
    return _dedup_filenames(results)[:top_k]


def retrieve_ticket(query: str, top_k: int) -> list[str]:
    """Run lookup_known_issues and return ranked unique filenames."""
    from src.retrieval.retriever import get_retriever
    retriever = get_retriever()
    results = retriever.lookup_known_issues(query, top_k=top_k * 3)
    return _dedup_filenames(results)[:top_k]


# ---------------------------------------------------------------------------
# Evaluation loop
# ---------------------------------------------------------------------------

def evaluate(
    gold: list[dict[str, Any]],
    pipeline: str,  # "process" | "ticket" | "both"
    top_k: int,
) -> dict[str, dict[str, float]]:
    """Run retrieval on all gold entries and compute aggregate metrics per pipeline."""
    results: dict[str, list[dict[str, Any]]] = {"process": [], "ticket": []}

    for entry in gold:
        p = entry["pipeline"]
        if pipeline != "both" and p != pipeline:
            continue

        query = entry["query"]
        relevant = entry["relevant_docs"]

        print(f"  [{entry['qid']}] {query[:60]}...", flush=True)

        if p == "process":
            retrieved = retrieve_process(query, top_k)
        else:
            retrieved = retrieve_ticket(query, top_k)

        results[p].append({
            "qid": entry["qid"],
            "query": query,
            "relevant": relevant,
            "retrieved": retrieved,
            "human_reviewed": entry.get("human_reviewed", False),
            "query_type": entry.get("query_type", "unknown"),
            "recall@3": recall_at_k(retrieved, relevant, 3),
            "mrr@5": reciprocal_rank(retrieved, relevant),
            "ndcg@5": ndcg_at_k(retrieved, relevant, 5),
            "ctx_precision": context_precision(retrieved, relevant, top_k),
            "ctx_recall": context_recall(retrieved, relevant, top_k),
        })

    metrics: dict[str, dict[str, float]] = {}
    for p_name, runs in results.items():
        if not runs:
            continue
        n = len(runs)
        metrics[p_name] = {
            "n": float(n),
            "recall@3": sum(r["recall@3"] for r in runs) / n,
            "mrr@5": sum(r["mrr@5"] for r in runs) / n,
            "ndcg@5": sum(r["ndcg@5"] for r in runs) / n,
            "ctx_precision": sum(r["ctx_precision"] for r in runs) / n,
            "ctx_recall": sum(r["ctx_recall"] for r in runs) / n,
        }
        # Targets
        metrics[p_name]["recall@3_target_met"] = float(
            metrics[p_name]["recall@3"] >= 0.85
        )
        metrics[p_name]["mrr@5_target_met"] = float(
            metrics[p_name]["mrr@5"] >= 0.80
        )

    return metrics


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _met(val: float, target: float) -> str:
    return "PASS" if val >= target else "FAIL"


def print_metrics(metrics: dict[str, dict[str, float]]) -> None:
    print("\n" + "=" * 70)
    print("RETRIEVAL METRICS")
    print("=" * 70)

    for pipeline, m in metrics.items():
        print(f"\n  Pipeline: {pipeline.upper()} ({int(m['n'])} queries)")
        print(f"  {'Metric':<25} {'Value':>8}  {'Target':>12}  {'Met':>6}")
        print(f"  {'-'*55}")
        print(f"  {'recall@3':<25} {m['recall@3']:>8.3f}  {'>= 0.85':>12}  {_met(m['recall@3'], 0.85):>6}")
        print(f"  {'MRR@5':<25} {m['mrr@5']:>8.3f}  {'>= 0.80':>12}  {_met(m['mrr@5'], 0.80):>6}")
        print(f"  {'NDCG@5':<25} {m['ndcg@5']:>8.3f}  {'(no target)':>12}  {'--':>6}")
        print(f"  {'RAGAS ctx precision':<25} {m['ctx_precision']:>8.3f}  {'(no target)':>12}  {'--':>6}")
        print(f"  {'RAGAS ctx recall':<25} {m['ctx_recall']:>8.3f}  {'(no target)':>12}  {'--':>6}")


def append_to_report(
    metrics: dict[str, dict[str, float]],
    top_k: int,
    gold_path: Path,
) -> None:
    """Append retrieval metrics section to eval/REPORT.md."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    n_gold = sum(int(m["n"]) for m in metrics.values())

    section = f"""

---

## Retrieval Metrics ({timestamp})

Evaluated against `{gold_path.name}` ({n_gold} queries total).
Top-k={top_k}. Two pipelines, one per architecture.

| Pipeline | recall@3 | MRR@5 | NDCG@5 | RAGAS ctx precision | RAGAS ctx recall |
|---|---|---|---|---|---|
"""
    for pipeline, m in metrics.items():
        r3 = f"{m['recall@3']:.3f}" + (" PASS" if m["recall@3"] >= 0.85 else " FAIL")
        mrr = f"{m['mrr@5']:.3f}" + (" PASS" if m["mrr@5"] >= 0.80 else " FAIL")
        section += (
            f"| {pipeline} | {r3} | {mrr} | {m['ndcg@5']:.3f} "
            f"| {m['ctx_precision']:.3f} | {m['ctx_recall']:.3f} |\n"
        )

    section += """
**Targets:** recall@3 ≥ 0.85 · MRR@5 ≥ 0.80

**RAGAS circularity mitigation:** queries use vocabulary-divergent paraphrases
(e.g., 'vacation days' instead of 'PTO', 'bulk import failed' instead of 'EIB load').
"""

    with REPORT_FILE.open("a", encoding="utf-8") as f:
        f.write(section)
    print(f"\nMetrics appended to {REPORT_FILE}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval")
    parser.add_argument("--gold", default=str(GOLD_FILE))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--pipeline", choices=["process", "ticket", "both"], default="both")
    parser.add_argument("--report", action="store_true", help="Append results to REPORT.md")
    parser.add_argument("--human-only", action="store_true", help="Only score human-reviewed pairs")
    args = parser.parse_args()

    gold_path = Path(args.gold)
    if not gold_path.exists():
        print(f"Gold set not found: {gold_path}")
        print("Run: uv run python eval/retrieval-gold/build_gold.py")
        sys.exit(1)

    gold = [json.loads(line) for line in gold_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    if args.human_only:
        gold = [g for g in gold if g.get("human_reviewed", False)]
        print(f"Evaluating {len(gold)} human-reviewed pairs only")

    print(f"Loaded {len(gold)} gold pairs from {gold_path}")
    print(f"Running retrieval (pipeline={args.pipeline}, top_k={args.top_k})...\n")

    metrics = evaluate(gold, args.pipeline, args.top_k)
    print_metrics(metrics)

    if args.report:
        append_to_report(metrics, args.top_k, gold_path)

    # Exit 1 if targets not met (for CI gate)
    for pipeline, m in metrics.items():
        if m["recall@3"] < 0.85 or m["mrr@5"] < 0.80:
            print(f"\n[WARN] {pipeline}: targets not met (recall@3={m['recall@3']:.3f}, MRR@5={m['mrr@5']:.3f})")
            sys.exit(1)

    print("\n[PASS] All retrieval targets met.")


if __name__ == "__main__":
    main()
