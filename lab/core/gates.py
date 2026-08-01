"""Pluggable gate/validate abstraction.

A gate is any callable ``(state) -> GateResult``. A gate node runs one or more
gates, and on failure sets ``failure_kind`` + ``raw_output`` so routing can send
control to the repair subgraph (see core.repair). Gates are opt-in: a workflow
only has them if its structure calls for validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .failures import FailureKind


@dataclass
class GateResult:
    ok: bool
    failure_kind: str = FailureKind.NONE.value
    summary: str = ""


Gate = Callable[[dict], GateResult]


def run_gate(name: str, check: Gate, state: dict) -> GateResult:
    """Run one gate, converting an exception into a failed GateResult."""
    try:
        return check(state)
    except Exception as exc:  # noqa: BLE001 - a gate must never crash the graph
        return GateResult(
            ok=False,
            failure_kind=FailureKind.GATE_FAILED.value,
            summary=f"{name}: {exc}",
        )


def as_state_update(name: str, result: GateResult) -> dict:
    """Translate a GateResult into a partial state update for a gate node."""
    return {
        "failure_kind": FailureKind.NONE.value if result.ok else result.failure_kind,
        "raw_output": "" if result.ok else result.summary,
        "log": [f"gate[{name}]: {'ok' if result.ok else 'FAILED'} · {result.summary}"],
    }
