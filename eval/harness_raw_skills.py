"""Harness B: replay the raw skills directly (no LangGraph), once per call.

Runs the same steps the estimation graph runs — orchestrator -> normalize ->
plan -> per-side estimate -> deterministic summary — as plain SEQUENTIAL
`claude_print` calls, each prompt augmented with the same node skill
(`NODE_SKILLS`) the graph attaches. The only difference from the graph harness
is the orchestration: no LangGraph state machine, no parallel fan-out, no merge
reducers. This isolates "does the graph orchestration change determinism vs raw
sequential skill calls" on the same input and the same execution path (claude CLI).

In DRY_RUN it returns the same fixtures as the graph, so the harness plumbing is
testable without spending `claude -p` sessions.
"""

from __future__ import annotations

import json
import os

from lab.core.claude_cli import claude_print
from lab.core.settings import settings
from lab.core.skills import with_skills
from lab.workflows.estimation import fixtures
from lab.workflows.estimation.nodes import (
    CANONICAL_SIDES,
    NODE_SKILLS,
    _SIDE_OF,
    _extract_json,
)


def _skilled(node: str, base: str) -> str:
    """Attach the node's skill (same mapping the graph uses) to a base prompt."""
    return with_skills(base, [NODE_SKILLS[node]])


def run_once(input_obj) -> dict:
    text = input_obj["input"] if isinstance(input_obj, dict) else str(input_obj)
    unit = (input_obj.get("unit") if isinstance(input_obj, dict) else None) or "hours"

    if settings.dry_run:
        sides = list(CANONICAL_SIDES)
        stories = fixtures.STORIES
        per_side = {s: fixtures.estimate_for(s, stories)["hours"] for s in sides}
    else:
        # 1. orchestrator — select sides
        op = _skilled(
            "estimate_orchestrator",
            "Given the feature brief below, which implementing sides are needed?\n"
            f"Choose from: {', '.join(CANONICAL_SIDES)}.\n"
            'Return a JSON array of the needed sides, e.g. ["backend", "qa"].\n\n'
            f"{text}",
        )
        picked = _extract_json(claude_print("estimate_orchestrator", op), [])
        sides = [s for s in CANONICAL_SIDES if s in picked] or list(CANONICAL_SIDES)

        # 2. normalize brief
        bp = _skilled(
            "brief_prd_input",
            "Clean up and normalize this feature brief/PRD text for downstream "
            f"planning. Return just the normalized text, nothing else:\n\n{text.strip()}",
        )
        brief = claude_print("brief_prd_input", bp).strip()

        # 3. plan stories
        sp = _skilled(
            "story_planner",
            "Decompose this feature brief into a short list of implementable "
            "stories. Return a JSON array of objects {id, title, acceptance_criteria}.\n\n"
            f"{brief}",
        )
        stories = _extract_json(claude_print("story_planner", sp), [])

        # 4. per-side estimate (sequential; the graph fans these out in parallel)
        per_side = {}
        for node, (side, label) in _SIDE_OF.items():
            base = (
                f"You are a senior {label} engineer estimating implementation effort.\n"
                f"For each story below, estimate the {label} effort in {unit}.\n"
                'Return a JSON object {"total": <number>, "breakdown": '
                '[{"story": <id>, "hours": <number>}]}. '
                f'If no {label} work is needed, return {{"total": 0, "breakdown": []}}.\n\n'
                f"Stories:\n{json.dumps(stories, indent=2)}"
            )
            parsed = _extract_json(claude_print(node, _skilled(node, base)), {})
            hours = float(parsed.get("total", 0) or 0) if isinstance(parsed, dict) else 0.0
            per_side[side] = hours if side in sides else 0.0

    # 5. summary — identical deterministic rule to the graph's estimate_summary numbers
    buffer_pct = float(os.getenv("ESTIMATION_RISK_BUFFER_PCT", "15"))
    per_side = {s: round(float(h), 1) for s, h in per_side.items()}
    subtotal = round(sum(per_side.values()), 1)
    total = round(subtotal * (1 + buffer_pct / 100), 1)

    return {
        "unit": unit,
        "sides": sides,
        "stories_count": len(stories),
        "per_side": per_side,
        "subtotal": subtotal,
        "total": total,
    }
