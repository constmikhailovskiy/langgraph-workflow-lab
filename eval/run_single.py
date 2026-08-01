"""Run ONE iteration of a harness on one input and write its result JSON.

The atomic unit the parallel eval workflow fans out: each workflow agent runs
this once and writes a file; aggregation reads the files deterministically
afterwards, so the measured numbers never pass through an LLM's summary.

    DRY_RUN=false python -m eval.run_single \
        --harness langgraph --input offline_workouts \
        --out eval/reports/_parallel/langgraph_1.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.inputs import sample_briefs


def _run_once(harness: str):
    if harness == "langgraph":
        from eval.harness_langgraph import run_once
    else:
        from eval.harness_raw_skills import run_once
    return run_once


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness", choices=["langgraph", "raw"], required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    run_once = _run_once(args.harness)
    iobj = sample_briefs.INPUTS[args.input]
    try:
        result = run_once(iobj)
    except Exception as exc:  # noqa: BLE001 - record, never crash the unit
        result = {"error": str(exc)}
    result["_harness"] = args.harness
    result["_input"] = args.input

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result))
    print(json.dumps({"ok": "error" not in result, "out": str(out), "total": result.get("total")}))


if __name__ == "__main__":
    main()
