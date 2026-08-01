"""Reusable markdown "skills" for LLM nodes and subagents.

A skill is a markdown file at ``lab/skills/<name>.md`` whose body is injected into
a node's prompt / system prompt. This mirrors how Claude Code skills feel, using
LangGraph's real extension point — the prompt — so any ``llm_step`` or
``subagent`` node can be handed reusable instructions without re-writing them.

Usage inside a node (real, non-DRY_RUN path):

    from lab.core.skills import with_skills
    prompt = with_skills("Give one concrete improvement:\\n\\n" + summary,
                         ["critique-checklist"])
    resp = llm_for("critique").invoke(prompt)

Or as a system prompt for a create_agent subagent:

    agent = create_agent(model, tools=[...],
                         system_prompt=with_skills(BASE_PROMPT, ["api-conventions"]))
"""

from __future__ import annotations

from pathlib import Path

#: lab/core/skills.py -> parents[1] == lab/ ; skills live in lab/skills/
SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"


class SkillNotFound(Exception):
    pass


def _strip_frontmatter(text: str) -> str:
    """Drop a leading ``---`` YAML frontmatter block, keeping only the body."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip("\n")
    return text


def load_skill(name: str) -> str:
    """Return the instruction body of skill ``name`` (frontmatter stripped)."""
    path = SKILLS_DIR / f"{name}.md"
    if not path.is_file():
        raise SkillNotFound(f"skill {name!r} not found in {SKILLS_DIR}")
    return _strip_frontmatter(path.read_text(encoding="utf-8")).strip()


def load_skills(names: list[str]) -> str:
    """Concatenate multiple skill bodies, separated by blank lines."""
    return "\n\n".join(load_skill(n) for n in names)


def with_skills(base_prompt: str, names: list[str] | None) -> str:
    """Append the named skills to a base/system prompt under a ``# Skills`` header.

    A no-op when ``names`` is empty, so nodes can always call it.
    """
    if not names:
        return base_prompt
    return f"{base_prompt}\n\n# Skills\n\n{load_skills(names)}"


def available_skills() -> list[str]:
    """List skill names present in lab/skills/ (without the .md extension)."""
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(
        p.stem for p in SKILLS_DIR.glob("*.md")
        if p.stem.lower() != "readme" and not p.stem.startswith("_")
    )
