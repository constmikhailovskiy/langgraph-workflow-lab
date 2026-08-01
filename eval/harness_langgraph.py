"""Harness A: run the estimation via the LangGraph graph, once per call."""

from __future__ import annotations

from lab.workflows.estimation.graph import graph


def run_once(input_obj) -> dict:
    """Invoke the estimation graph and normalize its result for metrics."""
    state = input_obj if isinstance(input_obj, dict) else {"input": input_obj}
    out = graph.invoke(state)
    summary = out.get("summary", {})
    return {
        "unit": summary.get("unit", "hours"),
        "sides": out.get("sides", []),
        "stories_count": len(out.get("stories", [])),
        "per_side": summary.get("per_side", {}),
        "subtotal": summary.get("subtotal", 0.0),
        "total": summary.get("total", 0.0),
    }
