"""Re-score existing eval results with the updated evaluator (fixed scorer).

Reads the traces.jsonl from a prior run and re-applies the evaluator.
Used when the scorer is updated between runs and a full re-run isn't possible
(e.g., API usage limit reached).

Usage:
    uv run python eval/rescore.py eval/results/run-20260603-130316/

Outputs:
    eval/results/run-{ts}-rescored/
        traces.jsonl  (passthrough — same events)
        summary.csv   (re-scored)
        meta.json     (updated with rescore metadata)
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    for _p in [_PROJECT_ROOT / ".env", _PROJECT_ROOT.parent.parent / ".env"]:
        if _p.exists():
            load_dotenv(_p, override=True)
            break
except ImportError:
    pass

from eval.evaluator import evaluate_single  # noqa: E402
from eval.run_eval import RESULTS_DIR, load_golden  # noqa: E402


def rescore(run_dir: Path) -> None:
    traces_path = run_dir / "traces.jsonl"
    meta_path = run_dir / "meta.json"
    if not traces_path.exists():
        print(f"traces.jsonl not found in {run_dir}")
        sys.exit(1)

    # Load original meta
    orig_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    k = orig_meta.get("k", 1)

    # Load golden for oracle labels
    golden_map = {g["id"]: g for g in load_golden()}

    # Reconstruct per-query results from traces
    with traces_path.open(encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]

    # Group events by (task_id, run)
    task_runs: dict[tuple, dict] = {}
    for e in events:
        tid = e.get("task_id", "")
        run_i = e.get("run", 1)
        key = (tid, run_i)
        if key not in task_runs:
            task_runs[key] = {"answer": "", "tools_called": [], "tool_calls": [], "turns": 0}
        if e["event"] == "agent_result":
            task_runs[key]["answer"] = e.get("answer", "")
            task_runs[key]["tools_called"] = e.get("tools_called", [])
            task_runs[key]["turns"] = e.get("turns", 0)
            # Note: tool_calls with args are NOT stored in traces
            # args checks will be skipped (args_ok defaults to True for re-score)

    # Collect task IDs in order
    task_ids: list[str] = []
    seen: set[str] = set()
    for e in events:
        tid = e.get("task_id", "")
        if tid and tid not in seen:
            task_ids.append(tid)
            seen.add(tid)

    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS_DIR / f"run-{ts}-rescored"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_fields = [
        "id", "type", "answer_type", "required_tools", "actual_tools",
        "usage_ok", "sequence_ok", "args_ok", "exec_ok", "failure_class",
        *[f"pass_run_{i+1}" for i in range(k)],
        "pass_at_k",
        "answer_preview",
    ]

    total = 0
    pass_at_k_count = 0
    routing_at_k_count = 0
    failure_counts: dict[str, int] = {}
    # tool -> {routing_pass, full_pass, total}
    per_tool_stats: dict[str, dict[str, int]] = {}
    rate_limit_count = 0

    with (out_dir / "summary.csv").open("w", newline="", encoding="utf-8") as sf:
        writer = csv.DictWriter(sf, fieldnames=csv_fields)
        writer.writeheader()

        for qid in task_ids:
            if qid not in golden_map:
                continue
            golden = golden_map[qid]

            run_evals = []
            # Map actual run number → pass, so CSV columns aren't mislabeled when
            # a middle run errored and was skipped.
            pass_by_run: dict[int, bool] = {}
            for run_i in range(1, k + 1):
                key = (qid, run_i)
                agent_result = task_runs.get(key, {})
                answer = agent_result.get("answer", "")

                # Skip rate-limit errors — don't count in totals
                if "[agent error" in answer:
                    rate_limit_count += 1
                    continue

                eval_row = evaluate_single(agent_result, golden, skip_args_check=True)
                run_evals.append(eval_row)
                pass_by_run[run_i] = eval_row["pass"]

            if not run_evals:
                continue  # All runs were errors

            total += 1
            passes = [e["pass"] for e in run_evals]
            pass_at_k = any(passes)
            if pass_at_k:
                pass_at_k_count += 1

            routing_ok = any(e["usage_ok"] and e["sequence_ok"] for e in run_evals)
            if routing_ok:
                routing_at_k_count += 1

            if pass_at_k:
                failure_class = "none"
            else:
                failure_class = Counter(
                    e["failure_class"] for e in run_evals
                ).most_common(1)[0][0]
            failure_counts[failure_class] = failure_counts.get(failure_class, 0) + 1

            for tool in golden["required_tools"]:
                stats = per_tool_stats.setdefault(
                    tool, {"routing_pass": 0, "full_pass": 0, "total": 0}
                )
                stats["total"] += 1
                if routing_ok:
                    stats["routing_pass"] += 1
                if pass_at_k:
                    stats["full_pass"] += 1

            first_eval = run_evals[0]
            csv_row = {
                "id": qid,
                "type": golden["type"],
                "answer_type": golden["answer_type"],
                "required_tools": "|".join(golden["required_tools"]),
                "actual_tools": "|".join(first_eval.get("actual_tools", [])),
                "usage_ok": first_eval["usage_ok"],
                "sequence_ok": first_eval["sequence_ok"],
                "args_ok": first_eval["args_ok"],
                "exec_ok": first_eval["exec_ok"],
                "failure_class": failure_class,
                **{f"pass_run_{i+1}": pass_by_run.get(i + 1, "n/a") for i in range(k)},
                "pass_at_k": pass_at_k,
                "answer_preview": first_eval.get("answer_preview", ""),
            }
            writer.writerow(csv_row)

    # Summary stats
    overall = pass_at_k_count / total if total else 0.0
    overall_routing = routing_at_k_count / total if total else 0.0
    per_tool_routing = {
        t: round(s["routing_pass"] / s["total"], 4) if s["total"] else 0.0
        for t, s in per_tool_stats.items()
    }
    per_tool_full_pass = {
        t: round(s["full_pass"] / s["total"], 4) if s["total"] else 0.0
        for t, s in per_tool_stats.items()
    }

    meta = {
        **orig_meta,
        "rescore_ts": datetime.now(UTC).isoformat(),
        "rescore_note": (
            "Re-scored with fixed evaluator: subsequence sequence check + "
            "token-split args matching. Rate-limit errors excluded from totals. "
            "Args check uses tools_called only (no args data in traces)."
        ),
        "total_queries_scored": total,
        "rate_limit_errors_excluded": rate_limit_count,
        "pass_at_k_count": pass_at_k_count,
        "overall_pass_at_k": round(overall, 4),
        "routing_at_k_count": routing_at_k_count,
        "overall_routing_at_k": round(overall_routing, 4),
        "per_tool_routing": per_tool_routing,
        "per_tool_full_pass": per_tool_full_pass,
        "failure_breakdown": failure_counts,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nRe-scored {total} queries ({rate_limit_count} rate-limit errors excluded)")
    print(f"routing@{k}:   {routing_at_k_count}/{total} = {overall_routing*100:.1f}%")
    print(f"full-pass@{k}: {pass_at_k_count}/{total} = {overall*100:.1f}%")
    print("Per-tool (routing / full-pass):")
    for tool in sorted(per_tool_stats):
        n = per_tool_stats[tool]["total"]
        print(f"  {tool:<32} routing {per_tool_routing[tool]*100:.1f}%  "
              f"full {per_tool_full_pass[tool]*100:.1f}%  ({n} queries)")
    print("Failure breakdown:")
    for fc, cnt in sorted(failure_counts.items(), key=lambda x: -x[1]):
        print(f"  {fc:<25} {cnt}")
    print(f"\nArtifacts: {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python eval/rescore.py <run_dir>")
        sys.exit(1)
    rescore(Path(sys.argv[1]))
