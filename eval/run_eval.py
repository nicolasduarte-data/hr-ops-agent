"""Evaluation harness runner.

Loads eval/golden/golden_set.jsonl, runs each query against the live agent
(k runs each for pass@k), applies step-level scoring, classifies failures,
and emits structured artifacts to eval/results/run-{timestamp}/.

Usage:
    uv run python eval/run_eval.py                  # full run, k=3
    uv run python eval/run_eval.py --k 1            # single pass, faster
    uv run python eval/run_eval.py --ids spd_001,lki_002  # specific queries
    uv run python eval/run_eval.py --dry-run        # validate golden set, no API calls
    uv run python eval/run_eval.py --category spd   # run one category

Output:
    eval/results/run-{timestamp}/
        traces.jsonl    — per-event structured log (task_start/result/eval/task_end)
        summary.csv     — one row per query with all scores
        meta.json       — run metadata (git commit, model, counts, pass@k)

pass@k definition: query passes if at least 1 of k runs achieves failure_class=="none".
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

# Add project root to sys.path so src.* imports resolve
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env before any src.agent.config import so ANTHROPIC_API_KEY resolves.
# Search: project root first, then workspace root (two levels up).
try:
    from dotenv import load_dotenv

    _env_candidates = [
        _PROJECT_ROOT / ".env",
        _PROJECT_ROOT.parent.parent / ".env",
    ]
    for _env_path in _env_candidates:
        if _env_path.exists():
            load_dotenv(_env_path, override=True)
            break
except ImportError:
    pass  # python-dotenv not installed; rely on shell env

from eval.evaluator import evaluate_single  # noqa: E402
from src.agent.config import LLM_MODEL  # noqa: E402
from src.agent.orchestrator import run_agent  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

GOLDEN_PATH = _PROJECT_ROOT / "eval" / "golden" / "golden_set.jsonl"
RESULTS_DIR = _PROJECT_ROOT / "eval" / "results"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def load_golden(
    ids_filter: set[str] | None = None,
    category_filter: str | None = None,
) -> list[dict]:
    entries = []
    with GOLDEN_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if ids_filter and entry["id"] not in ids_filter:
                continue
            if category_filter and not entry["id"].startswith(category_filter):
                continue
            entries.append(entry)
    return entries


def get_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_PROJECT_ROOT,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def emit(fp, event: dict) -> None:
    fp.write(json.dumps(event, ensure_ascii=False) + "\n")
    fp.flush()


def _repo_relative(p: Path) -> str:
    """Path as a repo-relative POSIX string so committed artifacts never leak an
    absolute local path. Falls back to the path's own POSIX form when it is
    outside the project tree (e.g. a pytest temp dir)."""
    try:
        return p.relative_to(_PROJECT_ROOT).as_posix()
    except ValueError:
        return p.as_posix()


# ─────────────────────────────────────────────────────────────────────────────
# Core eval loop
# ─────────────────────────────────────────────────────────────────────────────


def run_eval(
    golden_entries: list[dict],
    k: int,
    dry_run: bool,
    run_dir: Path,
) -> dict:
    """Run evaluation and write artifacts.  Returns summary stats dict."""

    run_dir.mkdir(parents=True, exist_ok=True)
    traces_path = run_dir / "traces.jsonl"
    summary_path = run_dir / "summary.csv"

    git_commit = get_git_commit()
    run_ts = datetime.now(UTC).isoformat()

    csv_fields = [
        "id", "type", "answer_type", "required_tools", "actual_tools",
        "usage_ok", "sequence_ok", "args_ok", "exec_ok", "failure_class",
        *[f"pass_run_{i+1}" for i in range(k)],
        "pass_at_k",
        "answer_preview",
    ]

    total = len(golden_entries)
    pass_at_k_count = 0
    routing_at_k_count = 0
    errored_count = 0
    failure_counts: dict[str, int] = {}
    # tool -> {routing_pass, full_pass, total}
    per_tool_stats: dict[str, dict[str, int]] = {}

    with traces_path.open("w", encoding="utf-8") as tf, \
         summary_path.open("w", newline="", encoding="utf-8") as sf:

        writer = csv.DictWriter(sf, fieldnames=csv_fields)
        writer.writeheader()

        for idx, golden in enumerate(golden_entries, 1):
            qid = golden["id"]
            instruction = golden["instruction"]
            logger.info("[%d/%d] %s  %s", idx, total, qid,
                        instruction[:70] + ("..." if len(instruction) > 70 else ""))

            emit(tf, {
                "event": "task_start",
                "task_id": qid,
                "instruction": instruction,
                "required_tools": golden["required_tools"],
                "run_ts": run_ts,
            })

            run_results = []
            run_evals = []

            for run_i in range(k):
                if dry_run:
                    # Fake result for schema validation
                    agent_result = {
                        "answer": "[dry-run]",
                        "tools_called": [],
                        "tool_calls": [],
                        "turns": 0,
                    }
                else:
                    t0 = time.monotonic()
                    try:
                        agent_result = run_agent(instruction)
                    except Exception as exc:
                        logger.error("  run %d AGENT ERROR: %s", run_i + 1, exc)
                        agent_result = {
                            "answer": f"[agent error: {exc}]",
                            "tools_called": [],
                            "tool_calls": [],
                            "turns": 0,
                        }
                    elapsed = time.monotonic() - t0
                    logger.debug("  run %d  elapsed=%.1fs  tools=%s",
                                 run_i + 1, elapsed, agent_result.get("tools_called"))

                run_results.append(agent_result)
                eval_row = evaluate_single(agent_result, golden)
                run_evals.append(eval_row)

                emit(tf, {
                    "event": "agent_result",
                    "task_id": qid,
                    "run": run_i + 1,
                    "answer": agent_result["answer"][:300],
                    "tools_called": agent_result["tools_called"],
                    "turns": agent_result.get("turns", 0),
                })
                emit(tf, {
                    "event": "evaluation",
                    "task_id": qid,
                    "run": run_i + 1,
                    "usage_ok": eval_row["usage_ok"],
                    "sequence_ok": eval_row["sequence_ok"],
                    "args_ok": eval_row["args_ok"],
                    "exec_ok": eval_row["exec_ok"],
                    "failure_class": eval_row["failure_class"],
                    "pass": eval_row["pass"],
                })

            # pass@k: full pass if at least one run achieves failure_class=="none"
            passes = [e["pass"] for e in run_evals]
            pass_at_k = any(passes)
            if pass_at_k:
                pass_at_k_count += 1

            # routing@k: routing (usage + sequence) correct in at least one run.
            # The real routing metric — separate from full pass, which also
            # requires answer-content match. (T1-3: emit both, don't conflate.)
            routing_ok = any(e["usage_ok"] and e["sequence_ok"] for e in run_evals)
            if routing_ok:
                routing_at_k_count += 1

            # Distinguish "scored" from "ran but every run errored" (e.g. quota).
            if all(r["answer"].startswith("[agent error") for r in run_results):
                errored_count += 1

            # Failure class: "none" if any run passed, else the most common
            # failure across the k runs (mode), not just the first run's class.
            if pass_at_k:
                failure_class = "none"
            else:
                failure_class = Counter(
                    e["failure_class"] for e in run_evals
                ).most_common(1)[0][0]
            failure_counts[failure_class] = failure_counts.get(failure_class, 0) + 1

            # Per-tool: track routing pass and full pass separately
            for tool in golden["required_tools"]:
                stats = per_tool_stats.setdefault(
                    tool, {"routing_pass": 0, "full_pass": 0, "total": 0}
                )
                stats["total"] += 1
                if routing_ok:
                    stats["routing_pass"] += 1
                if pass_at_k:
                    stats["full_pass"] += 1

            emit(tf, {
                "event": "task_end",
                "task_id": qid,
                "pass_at_k": pass_at_k,
                "failure_class": failure_class,
                "passes_per_run": passes,
            })

            # Write CSV row (use first run for display fields, worst for failure)
            first_eval = run_evals[0]
            csv_row = {
                "id": qid,
                "type": golden["type"],
                "answer_type": golden["answer_type"],
                "required_tools": "|".join(golden["required_tools"]),
                "actual_tools": "|".join(first_eval["actual_tools"]),
                "usage_ok": first_eval["usage_ok"],
                "sequence_ok": first_eval["sequence_ok"],
                "args_ok": first_eval["args_ok"],
                "exec_ok": first_eval["exec_ok"],
                "failure_class": failure_class,
                **{f"pass_run_{i+1}": passes[i] for i in range(k)},
                "pass_at_k": pass_at_k,
                "answer_preview": first_eval["answer_preview"],
            }
            writer.writerow(csv_row)

    # Build meta
    overall_pass_rate = pass_at_k_count / total if total else 0.0
    overall_routing_rate = routing_at_k_count / total if total else 0.0
    per_tool_routing = {
        tool: round(stats["routing_pass"] / stats["total"], 4) if stats["total"] else 0.0
        for tool, stats in per_tool_stats.items()
    }
    per_tool_full_pass = {
        tool: round(stats["full_pass"] / stats["total"], 4) if stats["total"] else 0.0
        for tool, stats in per_tool_stats.items()
    }
    categories_run = sorted({g["id"].split("_")[0] for g in golden_entries})

    meta = {
        "git_commit": git_commit,
        "model": LLM_MODEL,
        "run_ts": run_ts,
        "k": k,
        "dry_run": dry_run,
        "total_queries": total,
        "pass_at_k_count": pass_at_k_count,
        "overall_pass_at_k": round(overall_pass_rate, 4),
        "routing_at_k_count": routing_at_k_count,
        "overall_routing_at_k": round(overall_routing_rate, 4),
        "per_tool_routing": per_tool_routing,
        "per_tool_full_pass": per_tool_full_pass,
        "failure_breakdown": failure_counts,
        "coverage": {
            "scored": total,
            "errored_queries": errored_count,
            "categories_run": categories_run,
        },
        # Repo-relative, POSIX-style — never leak an absolute local path into
        # a committed artifact.
        "traces_path": _repo_relative(traces_path),
        "summary_path": _repo_relative(summary_path),
    }

    meta_path = run_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # Console summary
    logger.info("─" * 60)
    logger.info(
        "RESULTS  routing@%d: %d/%d = %.1f%%   full-pass@%d: %d/%d = %.1f%%",
        k, routing_at_k_count, total, overall_routing_rate * 100,
        k, pass_at_k_count, total, overall_pass_rate * 100,
    )
    logger.info("Per-tool (routing / full-pass, pass@%d):", k)
    for tool in sorted(per_tool_stats):
        n = per_tool_stats[tool]["total"]
        logger.info("  %-30s  routing %.1f%%  full %.1f%%  (%d queries)",
                    tool, per_tool_routing[tool] * 100,
                    per_tool_full_pass[tool] * 100, n)
    logger.info("Failure breakdown:")
    for fc, cnt in sorted(failure_counts.items(), key=lambda x: -x[1]):
        logger.info("  %-25s  %d", fc, cnt)
    logger.info("Artifacts: %s", run_dir)

    return meta


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="HR Ops Agent eval runner")
    p.add_argument("--k", type=int, default=3,
                   help="Number of runs per query for pass@k (default: 3)")
    p.add_argument("--ids", type=str, default="",
                   help="Comma-separated query IDs to run (default: all)")
    p.add_argument("--category", type=str, default="",
                   help="Run only queries with IDs starting with this prefix (e.g. spd, adv)")
    p.add_argument("--dry-run", action="store_true",
                   help="Validate golden set format without making API calls")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    ids_filter = set(args.ids.split(",")) if args.ids else None
    category_filter = args.category or None

    golden = load_golden(ids_filter=ids_filter, category_filter=category_filter)
    if not golden:
        logger.error("No golden entries matched the filter. Check --ids / --category.")
        sys.exit(1)

    logger.info("Loaded %d golden entries  k=%d  dry_run=%s", len(golden), args.k, args.dry_run)

    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    run_dir = RESULTS_DIR / f"run-{ts}"

    run_eval(golden, k=args.k, dry_run=args.dry_run, run_dir=run_dir)


if __name__ == "__main__":
    main()
