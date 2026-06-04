"""Golden set parity + policy-flag pins.

Guards against silent drift between build_golden.py (the generator) and the
committed golden_set.jsonl, and pins the out-of-scope refusal flags so the
policy_miss coverage cannot regress unnoticed.
"""

from __future__ import annotations

import json
import runpy
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_GOLDEN_FILE = _PROJECT_ROOT / "eval" / "golden" / "golden_set.jsonl"
_BUILD_SCRIPT = _PROJECT_ROOT / "eval" / "golden" / "build_golden.py"


def _generated() -> list[dict[str, Any]]:
    ns = runpy.run_path(str(_BUILD_SCRIPT))
    # Round-trip through json so types match the on-disk parse exactly.
    return [json.loads(json.dumps(e, ensure_ascii=False)) for e in ns["GOLDEN"]]


def _committed() -> list[dict[str, Any]]:
    lines = _GOLDEN_FILE.read_text(encoding="utf-8").splitlines()
    return [json.loads(ln) for ln in lines if ln.strip()]


def test_committed_matches_generator() -> None:
    assert _committed() == _generated()


def test_count_is_150() -> None:
    assert len(_committed()) == 150


def test_out_of_scope_queries_require_refusal() -> None:
    by_id = {e["id"]: e for e in _committed()}
    assert by_id["adv_025"]["requires_refusal"] is True
    assert by_id["adv_025"]["expected_answer_excludes"]  # non-empty leak guard
    assert by_id["adv_023"]["requires_refusal"] is True
