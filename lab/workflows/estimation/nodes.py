"""Nodes for the estimation workflow.

Flow: estimate_orchestrator -> brief_prd_input -> story_planner
      -> [be_estimate, frontend_estimate, qa_estimate, devops_estimate] (parallel)
      -> estimate_summary

Estimates a feature in `unit` (default "hours") per implementing side. The
orchestrator selects which sides are involved; each estimate node writes its own
`estimates[<side>]` key (dict-merge reducer), and the summary sums them with a
configurable risk buffer. Prompts are intentionally simple.
"""

from __future__ import annotations

import json
import os
import re

from lab.core.llm import llm_for
from lab.core.settings import settings
from lab.workflows.estimation import fixtures

CANONICAL_SIDES = fixtures.SIDES

# node name -> (canonical side, human label)
_SIDE_OF = {
    "be_estimate": ("backend", "Backend"),
    "frontend_estimate": ("frontend", "Frontend"),
    "qa_estimate": ("qa", "QA"),
    "devops_estimate": ("devops", "DevOps"),
}


def _extract_json(text: str, default):
    """Best-effort: pull the first JSON array/object out of an LLM reply."""
    try:
        m = re.search(r"(\[.*\]|\{.*\})", text, re.S)
        return json.loads(m.group(1)) if m else default
    except Exception:  # noqa: BLE001 - never crash a node on a bad reply
        return default


# --------------------------------------------------------------------------- #
# Setup + planning
# --------------------------------------------------------------------------- #


def estimate_orchestrator(state: dict) -> dict:
    """LLM side-selector: pick which of BE/FE/QA/DevOps the feature needs."""
    text = state.get("input", "")
    unit = state.get("unit") or "hours"
    if settings.dry_run:
        return {
            "unit": unit,
            "sides": list(CANONICAL_SIDES),
            "log": ["estimate_orchestrator: DRY_RUN (all sides)"],
        }
    prompt = (
        "Given the feature brief below, which implementing sides are needed?\n"
        f"Choose from: {', '.join(CANONICAL_SIDES)}.\n"
        'Return a JSON array of the needed sides, e.g. ["backend", "qa"].\n\n'
        f"{text}"
    )
    picked = _extract_json(llm_for("estimate_orchestrator").invoke(prompt).content, [])
    sides = [s for s in CANONICAL_SIDES if s in picked] or list(CANONICAL_SIDES)
    return {"unit": unit, "sides": sides, "log": [f"estimate_orchestrator: sides={sides}"]}


def brief_prd_input(state: dict) -> dict:
    """Normalize the raw brief/PRD input into `brief`."""
    brief = (state.get("input") or "").strip()
    return {"brief": brief, "log": ["brief_prd_input: normalized brief"]}


def story_planner(state: dict) -> dict:
    """Decompose the brief into implementable stories."""
    brief = state.get("brief", "")
    if settings.dry_run:
        return {
            "stories": fixtures.STORIES,
            "log": [f"story_planner: DRY_RUN {len(fixtures.STORIES)} stories"],
        }
    prompt = (
        "Decompose this feature brief into a short list of implementable user "
        "stories. Return a JSON array of objects {id, title, acceptance_criteria}.\n\n"
        f"{brief}"
    )
    stories = _extract_json(llm_for("story_planner").invoke(prompt).content, [])
    return {"stories": stories, "log": [f"story_planner: {len(stories)} stories"]}


# --------------------------------------------------------------------------- #
# Parallel per-side estimates
# --------------------------------------------------------------------------- #


def _estimate(state: dict, node: str) -> dict:
    side, label = _SIDE_OF[node]
    if side not in state.get("sides", CANONICAL_SIDES):
        return {
            "estimates": {side: {"hours": 0.0, "included": False, "breakdown": []}},
            "log": [f"{node}: skipped (side not selected)"],
        }
    stories = state.get("stories", [])
    unit = state.get("unit", "hours")
    if settings.dry_run:
        est = fixtures.estimate_for(side, stories)
        return {"estimates": {side: est}, "log": [f"{node}: DRY_RUN {est['hours']} {unit}"]}
    prompt = (
        f"You are a senior {label} engineer estimating implementation effort.\n"
        f"For each story below, estimate the {label} effort in {unit}.\n"
        'Return a JSON object {"total": <number>, "breakdown": '
        '[{"story": <id>, "hours": <number>}]}. If no {label} work is needed, '
        'return {"total": 0, "breakdown": []}.\n\n'
        f"Stories:\n{json.dumps(stories, indent=2)}"
    )
    parsed = _extract_json(llm_for(node).invoke(prompt).content, {})
    total = float(parsed.get("total", 0) or 0) if isinstance(parsed, dict) else 0.0
    breakdown = parsed.get("breakdown", []) if isinstance(parsed, dict) else []
    return {
        "estimates": {side: {"hours": total, "included": True, "breakdown": breakdown}},
        "log": [f"{node}: {total} {unit}"],
    }


def be_estimate(state: dict) -> dict:
    return _estimate(state, "be_estimate")


def frontend_estimate(state: dict) -> dict:
    return _estimate(state, "frontend_estimate")


def qa_estimate(state: dict) -> dict:
    return _estimate(state, "qa_estimate")


def devops_estimate(state: dict) -> dict:
    return _estimate(state, "devops_estimate")


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #


def estimate_summary(state: dict) -> dict:
    """Deterministic per-side + grand total in `unit`, with a risk buffer."""
    unit = state.get("unit", "hours")
    estimates = state.get("estimates", {})
    buffer_pct = float(os.getenv("ESTIMATION_RISK_BUFFER_PCT", "15"))

    per_side = {
        side: round(float(e.get("hours", 0.0)), 1)
        for side, e in estimates.items()
        if e.get("included", True)
    }
    subtotal = round(sum(per_side.values()), 1)
    total = round(subtotal * (1 + buffer_pct / 100), 1)

    lines = [f"Estimate ({unit}), risk buffer {buffer_pct:g}%:"]
    lines += [f"  - {side}: {hours}" for side, hours in sorted(per_side.items())]
    lines += [f"  subtotal: {subtotal}", f"  total (with buffer): {total}"]
    text = "\n".join(lines)

    summary = {
        "unit": unit,
        "per_side": per_side,
        "subtotal": subtotal,
        "risk_buffer_pct": buffer_pct,
        "total": total,
        "text": text,
    }
    return {"summary": summary, "log": [f"estimate_summary: total {total} {unit}"]}
