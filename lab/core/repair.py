"""Reusable, generic repair subgraph.

Opt-in utility: a workflow that has a gate can route a failure into a bounded
repair loop. It is generic over *how* a fix is attempted and re-checked, so it
carries no domain assumptions. Build one with your own callables:

    repair = build_repair_graph(attempt=my_fix, recheck=my_recheck)
    result = repair.invoke({"failure_kind": ..., "raw_output": ...})

In DRY_RUN the loop reports a synthetic repair so the topology stays walkable.
"""

from __future__ import annotations

from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from .settings import settings


class RepairState(TypedDict, total=False):
    failure_kind: str
    raw_output: str
    iteration: int
    budget: int
    repaired: bool
    reason: str


Attempt = Callable[[RepairState], dict]
Recheck = Callable[[RepairState], dict]


def build_repair_graph(attempt: Attempt, recheck: Recheck):
    """Compile a repair subgraph: inspect -> attempt_fix -> recheck -> (loop|END)."""

    def _inspect(state: RepairState) -> dict:
        return {
            "iteration": state.get("iteration", 0),
            "budget": state.get("budget", settings.repair_budget),
        }

    def _attempt(state: RepairState) -> dict:
        iteration = state.get("iteration", 0) + 1
        update = {} if settings.dry_run else (attempt(state) or {})
        return {"iteration": iteration, **update}

    def _recheck(state: RepairState) -> dict:
        if settings.dry_run:
            return {"repaired": True, "reason": "DRY_RUN: assumed repaired"}
        return recheck(state)

    def _route(state: RepairState) -> str:
        if state.get("repaired"):
            return END
        if state.get("iteration", 0) >= state.get("budget", settings.repair_budget):
            return END
        return "attempt_fix"

    builder = StateGraph(RepairState)
    builder.add_node("inspect", _inspect)
    builder.add_node("attempt_fix", _attempt)
    builder.add_node("recheck", _recheck)
    builder.add_edge(START, "inspect")
    builder.add_edge("inspect", "attempt_fix")
    builder.add_edge("attempt_fix", "recheck")
    builder.add_conditional_edges("recheck", _route, {"attempt_fix": "attempt_fix", END: END})
    return builder.compile()
