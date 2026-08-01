"""Nodes for the estimation workflow.

Flow: brief_prd_input -> story_planner
      -> [be_estimate, frontend_estimate, qa_estimate, devops_estimate] (parallel)
      -> estimate_summary

Estimates a feature in `unit` (default "hours") per implementing side.
`story_planner` decides which sides are involved itself, from the per-story
domain routing its skill already produces — there is no separate orchestrator
node. Each estimate node writes its own `estimates[<side>]` key (dict-merge
reducer), and the summary sums them with a configurable risk buffer. Prompts
are intentionally simple.

`NODE_SKILLS` below is the single, deterministic source of truth for which
skill each node attaches — no node inlines a skill name of its own. It mirrors
ORCHESTRATION.md in https://github.com/constmikhailovskiy/htbs-2-02-skills,
the repo these skills were imported from (`lab/skills/sources.json` tracks the
import for `python -m lab.core.skills --sync`), with two deliberate
departures: there is no `estimate_orchestrator` node (see below), and
`story_planner` uses `story-planner-hitl` rather than the source repo's own
`story-planner`. `wbs`, `story-planner`, and `estimate-orchestrator` were
imported too but aren't wired to any node — the source repo's own docs mark
`wbs` "not in the graph", `story-planner` is the placeholder
`story-planner-hitl` supersedes here, and `estimate-orchestrator`'s job (side
selection) is now `story_planner`'s, per the design below.

No side-selector node: `story-planner-hitl` already tags every story with
`domain_impact: {fe, be, qa, devops}` — routing metadata the skill produces
for exactly this purpose (see `references/output-contract.md`: "Each
estimator must receive: stories routed to its domain"). Re-deriving that same
routing with a second LLM call (the old `estimate_orchestrator` node) was
redundant and could disagree with the plan itself. `story_planner` now
computes `sides` as the union of domains any story maps to `True`, so side
selection is a single source of truth: the plan the estimators will actually
read from.

Known open thread (not something to silently "fix" here — surfaced, not
papered over): `frontend-estimate`'s SKILL.md is fully written and asks for a
three-point (optimistic/likely/pessimistic) per-story estimate against the
full `contracts/story.v1.md` shape, while `_estimate`/`estimate_summary` still
use the simpler `{"total": ..., "breakdown": [...]}` contract every other
estimate node expects. In practice the model follows the attached skill over
the base prompt, so `frontend_estimate` reliably comes back with no top-level
`total` key at all — `_estimate` below detects that (`shape_ok`), logs a
`WARNING` instead of silently recording 0 hours, and keeps the full,
unparsed reply in `estimates[side]["raw_reply"]` so the actual shape is
visible in Studio's state view. That's a diagnostic, not a fix: until
`estimate_summary` can reduce three-point estimates (and `story_planner` and
`frontend-estimate` agree on one story contract — see the `fe` vs `frontend`
key mismatch between `story-plan.schema.json`'s `domain_impact` and
`contracts/story.v1.md`'s), `frontend_estimate`'s hours will keep reading 0.
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

#: story-planner-hitl's domain_impact key -> our canonical side name.
_DOMAIN_TO_SIDE = {"fe": "frontend", "be": "backend", "qa": "qa", "devops": "devops"}

#: node name -> skill attached to its prompt. The single source of truth for
#: the node/skill mapping (see module docstring) — nodes read from this dict
#: rather than naming a skill inline.
NODE_SKILLS = {
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


def _sides_from_domain_impact(stories: list) -> list[str]:
    """Union of canonical sides any story's `domain_impact` maps to `True`.

    Falls back to every side when nothing is derivable (empty/malformed
    stories) — the same fail-open default the old `estimate_orchestrator`
    used, so an unparseable plan still gets a full estimate rather than none.
    """
    sides = {
        _DOMAIN_TO_SIDE[domain]
        for story in stories
        if isinstance(story, dict)
        for domain, on in (story.get("domain_impact") or {}).items()
        if on and domain in _DOMAIN_TO_SIDE
    }
    return sorted(sides) if sides else list(CANONICAL_SIDES)


# --------------------------------------------------------------------------- #
# Setup + planning
# --------------------------------------------------------------------------- #


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
    """Decompose the brief into stories and select sides (the `story-planner-hitl` skill).

    Parses the skill's own structured plan (`references/story-plan.schema.json`)
    rather than a plain story array, so each story's `domain_impact` is
    available to derive `sides` from — replacing the old `estimate_orchestrator`
    node. See the module docstring for why side selection lives here now.
    """
    brief = state.get("brief", "")
    if settings.dry_run:
        return {
            "stories": fixtures.STORIES,
            "sides": list(CANONICAL_SIDES),
            "log": [f"story_planner: DRY_RUN {len(fixtures.STORIES)} stories, all sides"],
        }
    prompt, skill, skill_state = _attach_skill(
        "story_planner",
        f"Decompose this feature brief/PRD into a story plan.\n\n{brief}",
    )
    plan = claude_print("story_planner", prompt)
    parsed = _extract_json(plan, {})
    stories = parsed.get("stories", []) if isinstance(parsed, dict) else []
    stories = stories if isinstance(stories, list) else []
    sides = _sides_from_domain_impact(stories)
    return {
        "stories": stories,
        "sides": sides,
        **skill_state,
        "log": [f"story_planner: skill={skill} {len(stories)} stories, sides={sides}"],
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
    reply = claude_print(node, prompt)
    parsed = _extract_json(reply, {})
    # A skill with its own opinionated output contract (e.g. frontend-estimate's
    # three-point optimistic/likely/pessimistic shape) can make the model ignore
    # the base prompt's {"total", "breakdown"} ask entirely. Detect that instead
    # of silently recording 0 hours: `raw_reply` always carries the full,
    # unparsed reply so the actual shape is visible in Studio's state view.
    shape_ok = isinstance(parsed, dict) and "total" in parsed
    total = float(parsed.get("total", 0) or 0) if isinstance(parsed, dict) else 0.0
    breakdown = parsed.get("breakdown", []) if isinstance(parsed, dict) else []

    if shape_ok:
        log_line = f"{node}: skill={skill} {total} {unit}"
    else:
        got = sorted(parsed) if isinstance(parsed, dict) else type(parsed).__name__
        log_line = (
            f"{node}: skill={skill} WARNING reply had no 'total' key (got {got}); "
            f"recorded 0 {unit} — see estimates['{side}']['raw_reply'] for the full reply"
        )

    if not included:
        return {
            "estimates": {side: {"hours": 0.0, "included": False, "breakdown": [], "raw_reply": reply}},
            **skill_state,
            "log": [f"{node}: skill={skill} skipped (side not selected)"],
        }
    return {
        "estimates": {side: {"hours": total, "included": True, "breakdown": breakdown, "raw_reply": reply}},
        **skill_state,
        "log": [log_line],
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
