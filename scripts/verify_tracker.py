#!/usr/bin/env python3
"""Mathematical progress tracker verifier (0% discrepancy between task ledger and reported completion %)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS_FILE = ROOT / "docs" / "IMPLEMENTATION_STATUS.json"


def verify() -> dict:
    data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    total_weight = 0.0
    verified_weight = 0.0
    phase_summary = {}

    for phase in data["phases"]:
        p_total = 0.0
        p_done = 0.0
        for task in phase["tasks"]:
            w = float(task["weight"])
            p_total += w
            if task["status"] == "verified":
                p_done += w
        pct = round((p_done / p_total) * 100.0, 1) if p_total > 0 else 0.0
        assert pct == phase["verified_pct"], (
            f"Phase {phase['id']} percentage mismatch: ledger has {phase['verified_pct']}%, math says {pct}%"
        )
        phase_summary[phase["id"]] = {"status": phase["status"], "verified_pct": pct}
        total_weight += p_total
        verified_weight += p_done

    overall_pct = round((verified_weight / total_weight) * 100.0, 1) if total_weight > 0 else 0.0
    assert overall_pct == data["overall_verified_pct"], (
        f"Overall percentage mismatch: ledger has {data['overall_verified_pct']}%, math says {overall_pct}%"
    )
    return {"overall_verified_pct": overall_pct, "phases": phase_summary}


if __name__ == "__main__":
    summary = verify()
    print(json.dumps(summary, indent=2))
