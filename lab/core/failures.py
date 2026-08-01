"""Failure taxonomy used by gates and the repair loop."""

from __future__ import annotations

from enum import Enum


class FailureKind(str, Enum):
    NONE = "none"
    LLM_ERROR = "llm_error"
    GATE_FAILED = "gate_failed"
    VALIDATION_FAILED = "validation_failed"


def is_failed(state: dict) -> bool:
    """True if state carries a real failure (not absent and not NONE)."""
    kind = state.get("failure_kind", FailureKind.NONE.value)
    return bool(kind) and kind != FailureKind.NONE.value
