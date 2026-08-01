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

import shutil
import subprocess
import tempfile
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


# --------------------------------------------------------------------------- #
# Importing skills from other repos / folders
# --------------------------------------------------------------------------- #


def _is_repo(source: str) -> bool:
    s = str(source)
    return s.endswith(".git") or "://" in s or s.startswith("git@")


def _collect(src: Path, names: list[str] | None) -> list[tuple[str, Path]]:
    """Find skill files in ``src``: flat ``<name>.md`` and nested ``<name>/SKILL.md``."""
    found: list[tuple[str, Path]] = []
    for p in sorted(src.glob("*.md")):
        if p.stem.lower() == "readme" or p.stem.startswith("_"):
            continue
        found.append((p.stem, p))
    for p in sorted(src.glob("*/SKILL.md")):  # Claude Code style
        found.append((p.parent.name, p))
    if names:
        wanted = set(names)
        found = [(n, p) for n, p in found if n in wanted]
    return found


def _copy_into_lab(pairs: list[tuple[str, Path]]) -> list[str]:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    imported = []
    for name, path in pairs:
        dest = SKILLS_DIR / f"{name}.md"
        if path.resolve() != dest.resolve():  # skip copying a file onto itself
            shutil.copyfile(path, dest)
        imported.append(name)
    return imported


def import_skills_from_dir(src_dir: str | Path, names: list[str] | None = None) -> list[str]:
    """Copy skill markdown files from a local folder into ``lab/skills/``."""
    src = Path(src_dir).expanduser().resolve()
    if not src.is_dir():
        raise FileNotFoundError(f"source folder not found: {src}")
    return _copy_into_lab(_collect(src, names))


def import_skills_from_repo(
    repo_url: str,
    subdir: str = "",
    names: list[str] | None = None,
    ref: str | None = None,
) -> list[str]:
    """Shallow-clone ``repo_url`` and import skills from ``subdir`` (or its root)."""
    with tempfile.TemporaryDirectory() as tmp:
        cmd = ["git", "clone", "--depth", "1"]
        if ref:
            cmd += ["--branch", ref]
        cmd += [repo_url, tmp]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"git clone failed: {proc.stderr.strip()}")
        src = Path(tmp) / subdir if subdir else Path(tmp)
        if not src.is_dir():
            raise FileNotFoundError(f"subdir {subdir!r} not found in {repo_url}")
        return _copy_into_lab(_collect(src, names))


def import_skills(
    source: str,
    subdir: str = "",
    names: list[str] | None = None,
    ref: str | None = None,
) -> list[str]:
    """Import skills from a git repo URL or a local folder.

    - Repo (URL ends with .git, has ``://``, or starts with ``git@``): clone,
      then read ``subdir`` (or the repo root).
    - Local folder: read ``source/subdir`` (or ``source``).

    Picks up flat ``<name>.md`` and nested ``<name>/SKILL.md`` files. Returns the
    imported skill names.
    """
    if _is_repo(source):
        return import_skills_from_repo(source, subdir=subdir, names=names, ref=ref)
    base = Path(source).expanduser()
    if subdir:
        base = base / subdir
    return import_skills_from_dir(base, names=names)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m lab.core.skills",
        description="Import skills into lab/skills/ from a git repo or a local folder.",
    )
    ap.add_argument("source", help="git repo URL, or a local folder path")
    ap.add_argument("--subdir", default="", help="folder within the repo/source to read from")
    ap.add_argument("--names", nargs="*", help="only import these skill names (without .md)")
    ap.add_argument("--ref", help="git branch/tag when source is a repo")
    args = ap.parse_args()

    imported = import_skills(args.source, subdir=args.subdir, names=args.names, ref=args.ref)
    listing = ", ".join(imported) if imported else "(none matched)"
    print(f"imported {len(imported)} skill(s) into {SKILLS_DIR}: {listing}")


if __name__ == "__main__":
    main()

