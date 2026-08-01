"""Nodes for the example workflow: summarize -> critique.

The copy-me reference: one llm_step (summarize), one llm_step that consumes the
first's output (critique). Each node checks settings.dry_run and returns a
fixture, otherwise calls its model via core.llm.llm_for. This is exactly the
shape the build-langgraph-workflow skill emits for generated llm_step nodes.
"""

from __future__ import annotations

from lab.core.llm import llm_for
from lab.core.settings import settings
from lab.workflows.example import fixtures


def summarize(state: dict) -> dict:
    text = state.get("input", "")
    if settings.dry_run:
        return {"summary": fixtures.SUMMARY, "log": ["summarize: DRY_RUN fixture"]}
    resp = llm_for("summarize").invoke(
        f"Summarize the following in 2-3 sentences:\n\n{text}"
    )
    return {"summary": resp.content, "log": ["summarize: llm ok"]}


def critique(state: dict) -> dict:
    summary = state.get("summary", "")
    if settings.dry_run:
        return {"critique": fixtures.CRITIQUE, "log": ["critique: DRY_RUN fixture"]}
    resp = llm_for("critique").invoke(
        f"Give one concrete improvement for this summary:\n\n{summary}"
    )
    return {"critique": resp.content, "log": ["critique: llm ok"]}
