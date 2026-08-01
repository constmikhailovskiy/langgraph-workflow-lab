"""Determinism metrics over N runs of the same input.

Headline number is the coefficient of variation (CV = stdev / mean): unitless, so
it compares directly across sides, inputs, and harnesses.
"""

from __future__ import annotations

import statistics

CANONICAL_SIDES = ["backend", "frontend", "qa", "devops"]


def summarize(values: list[float]) -> dict:
    """Spread stats for one series of numbers across runs."""
    vals = [float(v) for v in values]
    n = len(vals)
    if n == 0:
        return {"n": 0, "mean": 0.0, "min": 0.0, "max": 0.0, "range": 0.0, "stdev": 0.0, "cv": 0.0}
    mean = statistics.fmean(vals)
    lo, hi = min(vals), max(vals)
    stdev = statistics.stdev(vals) if n > 1 else 0.0
    cv = (stdev / mean) if mean else 0.0
    return {
        "n": n,
        "mean": round(mean, 2),
        "min": round(lo, 2),
        "max": round(hi, 2),
        "range": round(hi - lo, 2),
        "stdev": round(stdev, 3),
        "cv": round(cv, 4),
    }


def verdict(cv: float) -> str:
    """Plain-language determinism label for a CV."""
    if cv == 0:
        return "deterministic (0% CV)"
    if cv < 0.05:
        return "highly stable (<5% CV)"
    if cv < 0.15:
        return "moderately stable (5-15% CV)"
    if cv < 0.30:
        return "variable (15-30% CV)"
    return "highly variable (>30% CV)"


def aggregate(runs: list[dict]) -> dict:
    """Aggregate a list of normalized run-results (one input, one harness)."""
    if not runs:
        return {}
    # Per-side hours: 0 when a side wasn't selected in a run, so selection
    # nondeterminism is folded into the side's spread (and the total).
    per_side = {
        side: summarize([r.get("per_side", {}).get(side, 0.0) for r in runs])
        for side in CANONICAL_SIDES
    }
    # Side-selection stability.
    sets: dict[str, int] = {}
    for r in runs:
        key = ",".join(sorted(r.get("sides", []))) or "(none)"
        sets[key] = sets.get(key, 0) + 1

    return {
        "iterations": len(runs),
        "unit": runs[0].get("unit", "hours"),
        "per_side": per_side,
        "subtotal": summarize([r.get("subtotal", 0.0) for r in runs]),
        "total": summarize([r.get("total", 0.0) for r in runs]),
        "stories_count": summarize([r.get("stories_count", 0) for r in runs]),
        "side_selection": {"distinct": len(sets), "counts": sets},
    }
