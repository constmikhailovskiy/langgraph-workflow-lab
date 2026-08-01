"""Aggregate the per-iteration result files written by the parallel eval workflow.

Reads every eval/reports/_parallel/*.json (each one iteration of a harness),
groups by harness, and writes the same combined report.md + raw.json run_eval
produces — deterministically, straight from the files.

    python -m eval.aggregate_parallel offline_workouts_5x
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from eval import metrics
from eval.run_eval import render_markdown

PARALLEL_DIR = Path(__file__).resolve().parent / "reports" / "_parallel"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def main() -> None:
    stamp = sys.argv[1] if len(sys.argv) > 1 else "parallel"
    by_harness: dict = {}
    for f in sorted(PARALLEL_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        by_harness.setdefault(d.get("_harness", "?"), {}).setdefault(d.get("_input", "?"), []).append(d)

    # A run is a valid sample only if it actually produced an estimate. A
    # degenerate run (no stories / total 0) is an infra failure — usually the
    # story_planner call rate-limited under high concurrency — not estimate
    # variance, so it is excluded from the spread and counted separately.
    def _valid(r: dict) -> bool:
        return "error" not in r and r.get("stories_count", 0) > 0 and r.get("total", 0) > 0

    results: dict = {}
    iterations = 0
    for harness, inputs in by_harness.items():
        results[harness] = {}
        for iname, runs in inputs.items():
            good = [r for r in runs if _valid(r)]
            iterations = max(iterations, len(good))
            results[harness][iname] = {
                "runs": runs,
                "errors": len(runs) - len(good),
                "aggregate": metrics.aggregate(good),
            }

    outdir = REPORTS_DIR / stamp
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "raw.json").write_text(
        json.dumps({"iterations": iterations, "dry_run": False, "results": results}, indent=2)
    )
    md = render_markdown(results, iterations, dry_run=False)
    (outdir / "report.md").write_text(md)
    print(f"wrote {outdir}/report.md\n")
    print(md)


if __name__ == "__main__":
    main()
