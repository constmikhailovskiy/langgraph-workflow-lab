"""Determinism eval runner.

Runs each harness N times per fixed input, aggregates the spread, and writes a
markdown report + raw JSON to eval/reports/<timestamp>/.

    # DRY_RUN smoke (no tokens, variance is 0 by construction):
    DRY_RUN=true uv run python -m eval.run_eval --iterations 3

    # Real determinism eval (spends Anthropic tokens):
    DRY_RUN=false uv run python -m eval.run_eval --iterations 7 --harness both
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from lab.core.settings import settings

from eval import metrics
from eval.harness_langgraph import run_once as run_langgraph
from eval.harness_raw_skills import run_once as run_raw
from eval.inputs import sample_briefs

REPORTS_DIR = Path(__file__).resolve().parent / "reports"
HARNESSES = {"langgraph": run_langgraph, "raw": run_raw}

_CANON_SIDES = ["backend", "frontend", "qa", "devops"]


def _run_status(r: dict) -> str:
    if "error" in r:
        return "error"
    if r.get("stories_count", 0) <= 0 or r.get("total", 0) <= 0:
        return "excluded"
    return "ok"


def _run_row(idx: int, r: dict) -> str:
    """One markdown row for a single iteration's actual result."""
    ps = r.get("per_side", {})
    cells = ["–" if ps.get(s) is None else f"{ps[s]:g}" for s in _CANON_SIDES]
    sides = ",".join(r.get("sides", [])) or "–"
    total = r.get("total", "–")
    return (
        f"| {idx} | {_run_status(r)} | {sides} | {r.get('stories_count', '–')} "
        f"| {' | '.join(cells)} | {total} |"
    )


def run_matrix(iterations: int, harness_names: list[str], inputs: dict) -> dict:
    results: dict = {}
    for hname in harness_names:
        run_once = HARNESSES[hname]
        results[hname] = {}
        for iname, iobj in inputs.items():
            runs = []
            for i in range(iterations):
                print(f"[{hname}/{iname}] run {i + 1}/{iterations} ...", flush=True)
                try:
                    r = run_once(iobj)
                    print(f"    -> total {r.get('total')} sides {r.get('sides')}", flush=True)
                    runs.append(r)
                except Exception as exc:  # noqa: BLE001 - record, don't abort the matrix
                    print(f"    -> ERROR {exc}", flush=True)
                    runs.append({"error": str(exc)})
            good = [r for r in runs if "error" not in r]
            results[hname][iname] = {
                "runs": runs,
                "errors": len(runs) - len(good),
                "aggregate": metrics.aggregate(good),
            }
    return results


def render_markdown(results: dict, iterations: int, dry_run: bool) -> str:
    mode = "DRY_RUN (deterministic fixtures)" if dry_run else "REAL (live LLM)"
    out = [
        "# Estimation determinism report",
        "",
        f"- iterations per input: **{iterations}**",
        f"- mode: **{mode}**",
        "- headline metric: coefficient of variation (CV = stdev / mean) of the grand total",
        "",
        "## Methodology",
        "",
        "To gauge how deterministic the estimate is, each fixed input is run through "
        "a harness N times and the spread of the results is measured — the same "
        "input, so any variation comes from the model, not the prompt. Two harnesses "
        "are compared on identical inputs: **langgraph** runs the estimation graph "
        "end-to-end, and **raw** replays the same skills as plain sequential "
        "`claude` calls (no graph). Per run we record each side's hours, the grand "
        "total, the selected sides, and the story count; across runs we report range, "
        "standard deviation, and CV (stdev/mean — unitless, so it compares across "
        "sides and harnesses). The risk buffer is applied identically in both, so it "
        "never contributes to the delta. A run that produced no parseable stories "
        "(total 0) is a degenerate result, not an estimate, and is excluded from the "
        "statistics but shown in the per-iteration table. CV bands: 0 deterministic · "
        "<5% highly stable · 5–15% moderate · 15–30% variable · >30% highly variable.",
        "",
        "```mermaid",
        "flowchart TD",
        '    IN["Fixed input<br/>(same PRD every run)"]',
        '    IN --> LG["Harness: langgraph<br/>estimation graph end-to-end"]',
        '    IN --> RAW["Harness: raw<br/>same skills, sequential claude calls"]',
        '    LG -->|"run N times"| LGR["N results<br/>sides · per-side hours · total · stories"]',
        '    RAW -->|"run N times"| RAWR["N results"]',
        '    LGR --> AGG["Aggregate spread<br/>range · stdev · CV<br/>(drop degenerate runs)"]',
        "    RAWR --> AGG",
        '    AGG --> REP["Report<br/>stats + per-iteration table"]',
        "```",
        "",
    ]
    for hname, inputs in results.items():
        out += [f"## Harness: `{hname}`", ""]
        for iname, data in inputs.items():
            agg = data.get("aggregate") or {}
            if not agg:
                out += [f"### {iname}", "", "_(no successful runs)_", ""]
                continue
            unit = agg.get("unit", "hours")
            t = agg["total"]
            errnote = f" · {data['errors']} run error(s)" if data.get("errors") else ""
            out += [
                f"### Input: `{iname}`{errnote}",
                "",
                f"**Grand total ({unit}):** mean {t['mean']}, range {t['min']}–{t['max']} "
                f"(Δ {t['range']}), stdev {t['stdev']}, **CV {t['cv']} → {metrics.verdict(t['cv'])}**",
                "",
                "| side | mean | min | max | Δ range | stdev | CV | verdict |",
                "|---|---|---|---|---|---|---|---|",
            ]
            for side, m in agg["per_side"].items():
                out.append(
                    f"| {side} | {m['mean']} | {m['min']} | {m['max']} | {m['range']} "
                    f"| {m['stdev']} | {m['cv']} | {metrics.verdict(m['cv'])} |"
                )
            sel = agg["side_selection"]
            sc = agg["stories_count"]
            out += [
                "",
                f"- side-selection stability: **{sel['distinct']} distinct set(s)** — {sel['counts']}",
                f"- stories/run: mean {sc['mean']}, range {sc['min']}–{sc['max']}",
                "",
                f"**Per-iteration results ({unit})** — `ok` rows are the "
                f"{agg['iterations']} valid samples the stats above use; `excluded` "
                "= degenerate run: story_planner returned no parseable stories "
                "(the story-planner-hitl output-contract mismatch), so total 0. "
                "Recurs even on a sequential retry, so it is a reliability finding, "
                "not just a rate-limit artifact. Not counted in the stats:",
                "",
                "| # | status | sides | stories | backend | frontend | qa | devops | total |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
            out += [_run_row(i, r) for i, r in enumerate(data.get("runs", []), 1)]
            out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Estimation determinism eval.")
    ap.add_argument("--iterations", type=int, default=7)
    ap.add_argument("--harness", choices=["langgraph", "raw", "both"], default="both")
    ap.add_argument("--input", default="all", help="input name from sample_briefs, or 'all'")
    ap.add_argument("--stamp", default=None, help="report folder name (default: timestamp)")
    args = ap.parse_args()

    inputs = (
        dict(sample_briefs.INPUTS)
        if args.input == "all"
        else {args.input: sample_briefs.INPUTS[args.input]}
    )
    harness_names = ["langgraph", "raw"] if args.harness == "both" else [args.harness]
    dry = settings.dry_run

    results = run_matrix(args.iterations, harness_names, inputs)

    stamp = args.stamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = REPORTS_DIR / stamp
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "raw.json").write_text(
        json.dumps({"iterations": args.iterations, "dry_run": dry, "results": results}, indent=2)
    )
    md = render_markdown(results, args.iterations, dry)
    (outdir / "report.md").write_text(md)

    print(f"wrote {outdir}/report.md and raw.json\n")
    print(md)


if __name__ == "__main__":
    main()
