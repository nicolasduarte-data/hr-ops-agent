"""run_eval emits routing + full-pass + coverage separately.

Uses dry_run=True so there are no API calls — this verifies the aggregation
and artifact emission, not live agent behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eval.run_eval import run_eval


def _entry(qid: str, tool: str) -> dict[str, Any]:
    return {
        "id": qid,
        "type": "tool_use",
        "instruction": "test",
        "allowed_tools": [],
        "required_tools": [tool],
        "expected_tool_sequence": [{"tool": tool, "args_contains": {}}],
        "expected_answer_contains": [],
        "expected_answer_excludes": [],
        "answer_type": "factual",
        "notes": "",
        "requires_refusal": False,
    }


def test_meta_emits_routing_fullpass_and_coverage(tmp_path: Path) -> None:
    golden = [
        _entry("spd_001", "search_process_docs"),
        _entry("lki_001", "lookup_known_issues"),
    ]
    run_dir = tmp_path / "run"
    meta = run_eval(golden, k=1, dry_run=True, run_dir=run_dir)

    # T1-3: routing and full-pass are distinct fields; the old conflated name is gone.
    assert "per_tool_routing" in meta
    assert "per_tool_full_pass" in meta
    assert "overall_routing_at_k" in meta
    assert "per_tool_accuracy" not in meta

    # Coverage block distinguishes scored vs errored and lists categories.
    assert meta["coverage"]["scored"] == 2
    assert meta["coverage"]["errored_queries"] == 0
    assert set(meta["coverage"]["categories_run"]) == {"spd", "lki"}

    # dry-run yields empty tools_called → routing fails for every query.
    assert meta["overall_routing_at_k"] == 0.0
    assert meta["per_tool_routing"]["search_process_docs"] == 0.0

    # Artifacts written and meta round-trips from disk.
    assert (run_dir / "meta.json").exists()
    assert (run_dir / "summary.csv").exists()
    assert (run_dir / "traces.jsonl").exists()
    written = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert written["overall_routing_at_k"] == 0.0
