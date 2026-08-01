"""Base state shared by every workflow.

A workflow's own State should subclass WorkflowState and add its artifact fields:

    class MyState(WorkflowState, total=False):
        prd: str
        tasks: list[dict]
"""

from __future__ import annotations

from typing import Annotated, TypedDict


def append(left: list | None, right: list | None) -> list:
    """Reducer: concatenate list updates instead of overwriting.

    Lets every node append to `log` without clobbering earlier entries.
    """
    return (left or []) + (right or [])


def merge(left: dict | None, right: dict | None) -> dict:
    """Reducer: shallow-merge dict updates.

    Lets parallel nodes each write their own key of a shared dict (e.g. four
    estimate nodes writing `estimates[<side>]`) without a write conflict.
    """
    return {**(left or {}), **(right or {})}


class WorkflowState(TypedDict, total=False):
    #: Free-form entry point text (brief, prompt, PRD, ...).
    input: str
    #: Human-readable trace, appended to by every node.
    log: Annotated[list[str], append]
    #: Set by gate nodes; "none" (or absent) means healthy. See core.failures.
    failure_kind: str
    #: Raw output captured from a failed gate/check, fed to repair.
    raw_output: str
