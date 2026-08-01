"""Nodes for the estimation workflow.

Flow: estimate_orchestrator -> brief_prd_input -> story_planner
      -> [be_estimate, frontend_estimate, qa_estimate, devops_estimate] (parallel)
      -> estimate_summary

Estimates a feature in `unit` (default "hours") per implementing side. The
orchestrator selects which sides are involved; each estimate node writes its own
`estimates[<side>]` key (dict-merge reducer), and the summary sums them with a
configurable risk buffer. Prompts are intentionally simple.

`NODE_SKILLS` below is the single, deterministic source of truth for which
skill each node attaches — no node inlines a skill name of its own. It mirrors
ORCHESTRATION.md in https://github.com/constmikhailovskiy/htbs-2-02-skills,
the repo these skills were imported from (`lab/skills/sources.json` tracks the
import for `python -m lab.core.skills --sync`), with one deliberate override:
`story_planner` uses `story-planner-hitl` rather than the source repo's own
`story-planner` (its plain, `story-planner`-named graph entry). `wbs` and
`story-planner` were imported too but aren't wired to any node — the source
repo's own docs mark `wbs` "not in the graph", and `story-planner` is the
thinner placeholder `story-planner-hitl` supersedes here.

Known open threads (not something to silently "fix" here — surfaced so the
mismatch is visible instead of discovered at run time):

- `frontend-estimate`'s SKILL.md is fully written and asks for a three-point
  (optimistic/likely/pessimistic) per-story estimate against the full
  `contracts/story.v1.md` shape, while this module's base prompt and
  `_estimate`/`estimate_summary` still use the simpler
  `{"total": ..., "breakdown": [...]}` contract every other estimate node
  expects. Until `story_planner` emits the full story contract and
  `estimate_summary` can reduce three-point estimates, that skill's
  instructions partially conflict with the base prompt it's attached to.
- `story-planner-hitl` mandates two human-in-the-loop approval gates
  (`scope_review`, `readiness_approval`) and expects the caller to persist a
  `decision_log` and resume only on an explicit human decision event. This
  node is a single `claude_print` call with no pause/resume mechanism (no
  `interrupt()`, no checkpointer) — it will get back a structured payload
  that names a gate status instead of a plain story list, and `story_planner`
  still naively `_extract_json`s a story array out of whatever comes back.
  Honoring the gates for real needs a LangGraph `interrupt()`-based node and a
  checkpointer; that's a bigger change than swapping the attached skill.
"""

from __future__ import annotations

import json
import os
import re

from lab.core.claude_cli import claude_print
from lab.core.settings import settings
from lab.core.skills import with_skills
from lab.workflows.estimation import fixtures

CANONICAL_SIDES = fixtures.SIDES

#: node name -> skill attached to its prompt. The single source of truth for
#: the node/skill mapping (see module docstring) — nodes read from this dict
#: rather than naming a skill inline.
NODE_SKILLS = {
    "estimate_orchestrator": "estimate-orchestrator",
    "brief_prd_input": "brief-prd-input",
    "story_planner": "story-planner-hitl",
    "be_estimate": "be-estimate",
    "frontend_estimate": "frontend-estimate",
    "qa_estimate": "qa-estimate",
    "devops_estimate": "devops-estimate",
    "estimate_summary": "estimate-summary",
}

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


def _attach_skill(node: str, base_prompt: str) -> tuple[str, str, dict]:
    """Attach `node`'s skill (per `NODE_SKILLS`) to `base_prompt`, return proof it ran.

    Returns ``(prompt, skill, skill_state)``: the skill name comes from the
    single `NODE_SKILLS` mapping, never a per-call literal, so a node cannot
    accidentally attach the wrong skill. `skill_state["skills_used"][node]`
    (merged into graph state, see `EstimationState.skills_used`) is durable
    evidence a real node run actually attached its skill, independent of the
    LLM reply content.
    """
    skill = NODE_SKILLS[node]
    return with_skills(base_prompt, [skill]), skill, {"skills_used": {node: [skill]}}


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
    prompt, skill, skill_state = _attach_skill(
        "estimate_orchestrator",
        "Given the feature brief below, which implementing sides are needed?\n"
        f"Choose from: {', '.join(CANONICAL_SIDES)}.\n"
        'Return a JSON array of the needed sides, e.g. ["backend", "qa"].\n\n'
        f"{text}",
    )
    picked = _extract_json(claude_print("estimate_orchestrator", prompt), [])
    sides = [s for s in CANONICAL_SIDES if s in picked] or list(CANONICAL_SIDES)
    return {
        "unit": unit,
        "sides": sides,
        **skill_state,
        "log": [f"estimate_orchestrator: skill={skill} sides={sides}"],
    }


def brief_prd_input(state: dict) -> dict:
    """Normalize the raw brief/PRD input into `brief`."""
    raw = (state.get("input") or "").strip()
    if settings.dry_run:
        return {"brief": raw, "log": ["brief_prd_input: normalized brief"]}
    prompt, skill, skill_state = _attach_skill(
        "brief_prd_input",
        "Clean up and normalize this feature brief/PRD text for downstream "
        f"planning. Return just the normalized text, nothing else:\n\n{raw}",
    )
    brief = claude_print("brief_prd_input", prompt).strip()
    return {
        "brief": brief,
        **skill_state,
        "log": [f"brief_prd_input: skill={skill} normalized brief"],
    }


def story_planner(state: dict) -> dict:
    """Decompose the brief into implementable stories (the `story-planner-hitl` skill).

    See the module docstring's "open threads" note: this single-pass node does
    not implement the skill's mandatory human-in-the-loop approval gates.
    """
    brief = state.get("brief", "")
    if settings.dry_run:
        return {
            "stories": fixtures.STORIES,
            "log": [f"story_planner: DRY_RUN {len(fixtures.STORIES)} stories"],
        }
    prompt, skill, skill_state = _attach_skill(
        "story_planner",
        "Decompose this feature brief into a short list of implementable "
        "stories. Return a JSON array of objects {id, title, acceptance_criteria}.\n\n"
        f"{brief}",
    )
    stories = _extract_json(claude_print("story_planner", prompt), [])
    return {
        "stories": stories,
        **skill_state,
        "log": [f"story_planner: skill={skill} {len(stories)} stories"],
    }


# --------------------------------------------------------------------------- #
# Parallel per-side estimates
# --------------------------------------------------------------------------- #


def _estimate(state: dict, node: str) -> dict:
    side, label = _SIDE_OF[node]
    included = side in state.get("sides", CANONICAL_SIDES)
    stories = state.get("stories", [])
    unit = state.get("unit", "hours")

    if settings.dry_run:
        if not included:
            return {
                "estimates": {side: {"hours": 0.0, "included": False, "breakdown": []}},
                "log": [f"{node}: skipped (side not selected)"],
            }
        est = fixtures.estimate_for(side, stories)
        return {"estimates": {side: est}, "log": [f"{node}: DRY_RUN {est['hours']} {unit}"]}

    # Every estimate node runs a real claude -p session, even when its side
    # wasn't selected, so the host session always sees all four sides estimated.
    prompt, skill, skill_state = _attach_skill(
        node,
        f"You are a senior {label} engineer estimating implementation effort.\n"
        f"For each story below, estimate the {label} effort in {unit}.\n"
        'Return a JSON object {"total": <number>, "breakdown": '
        '[{"story": <id>, "hours": <number>}]}. '
        f"If no {label} work is needed, return {{\"total\": 0, \"breakdown\": []}}.\n\n"
        f"Stories:\n{json.dumps(stories, indent=2)}",
    )
    parsed = _extract_json(claude_print(node, prompt), {})
    total = float(parsed.get("total", 0) or 0) if isinstance(parsed, dict) else 0.0
    breakdown = parsed.get("breakdown", []) if isinstance(parsed, dict) else []

    if not included:
        return {
            "estimates": {side: {"hours": 0.0, "included": False, "breakdown": []}},
            **skill_state,
            "log": [f"{node}: skill={skill} skipped (side not selected)"],
        }
    return {
        "estimates": {side: {"hours": total, "included": True, "breakdown": breakdown}},
        **skill_state,
        "log": [f"{node}: skill={skill} {total} {unit}"],
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

    skill_state: dict = {}
    if settings.dry_run:
        text = "\n".join(lines)
        log_line = f"estimate_summary: DRY_RUN total {total} {unit}"
    else:
        prompt, skill, skill_state = _attach_skill(
            "estimate_summary",
            "Write a short plain-text summary of this effort estimate for a "
            f"stakeholder. Unit: {unit}. Per-side hours: {json.dumps(per_side)}. "
            f"Subtotal: {subtotal}. Risk buffer: {buffer_pct:g}%. "
            f"Total with buffer: {total}.",
        )
        text = claude_print("estimate_summary", prompt).strip()
        log_line = f"estimate_summary: skill={skill} total {total} {unit}"

    summary = {
        "unit": unit,
        "per_side": per_side,
        "subtotal": subtotal,
        "risk_buffer_pct": buffer_pct,
        "total": total,
        "text": text,
    }
    return {"summary": summary, **skill_state, "log": [log_line]}
