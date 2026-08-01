"""Reusable "skills" for LLM nodes and subagents, following the open Agent Skills
standard (https://agentskills.io/specification).

A skill is a directory at ``lab/skills/<name>/SKILL.md`` — YAML frontmatter
(``name``, ``description``, ...) followed by a Markdown instruction body, plus
optional ``scripts/``, ``references/``, ``assets/`` subdirectories. This mirrors
how Claude Code and other agentskills.io-compatible clients load skills, using
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

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

#: lab/core/skills.py -> parents[1] == lab/ ; skills live in lab/skills/
SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"

SKILL_FILE = "SKILL.md"
SOURCES_FILE = "sources.json"


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
    """Return the instruction body of skill ``name`` (frontmatter stripped).

    Looks up ``lab/skills/<name>/SKILL.md`` per the Agent Skills directory
    layout (a skill is a folder, not a bare markdown file).
    """
    path = SKILLS_DIR / name / SKILL_FILE
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
    """List skill names present in lab/skills/ (directories with a SKILL.md)."""
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(p.parent.name for p in SKILLS_DIR.glob(f"*/{SKILL_FILE}"))


# --------------------------------------------------------------------------- #
# Importing skills from other repos / folders
# --------------------------------------------------------------------------- #


def _is_repo(source: str) -> bool:
    s = str(source)
    return s.endswith(".git") or "://" in s or s.startswith("git@")


def _collect(src: Path, names: list[str] | None) -> list[tuple[str, Path]]:
    """Find skill directories under ``src``: nested ``<name>/SKILL.md``, or
    ``src`` itself being a single skill's root (a bare ``SKILL.md`` at its top).
    """
    found: list[tuple[str, Path]] = []
    root_skill = src / SKILL_FILE
    if root_skill.is_file():
        found.append((src.name, src))
    for p in sorted(src.glob(f"*/{SKILL_FILE}")):
        found.append((p.parent.name, p.parent))
    if names:
        wanted = set(names)
        found = [(n, p) for n, p in found if n in wanted]
    return found


def _copy_into_lab(pairs: list[tuple[str, Path]]) -> list[str]:
    """Copy each skill's whole directory (SKILL.md + scripts/references/assets)
    into ``lab/skills/<name>/``.
    """
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    imported = []
    for name, src_dir in pairs:
        dest = SKILLS_DIR / name
        if src_dir.resolve() != dest.resolve():  # skip copying a skill onto itself
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src_dir, dest)
        imported.append(name)
    return imported


# --------------------------------------------------------------------------- #
# Tracking sources, so a later run can pull upstream updates (`--sync`)
# --------------------------------------------------------------------------- #


def _sources_path() -> Path:
    return SKILLS_DIR / SOURCES_FILE


def _load_sources() -> list[dict]:
    path = _sources_path()
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save_sources(sources: list[dict]) -> None:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    _sources_path().write_text(json.dumps(sources, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _record_source(source: str, subdir: str, ref: str | None, names: list[str] | None) -> None:
    """Remember an import call so `sync_skills()` can re-run it later.

    Keyed on (source, subdir, ref); a repeat import of the same source/subdir/ref
    overwrites the previously recorded `names` rather than duplicating the entry.
    """
    sources = _load_sources()
    for entry in sources:
        if (entry["source"], entry.get("subdir", ""), entry.get("ref")) == (source, subdir, ref):
            entry["names"] = names
            break
    else:
        sources.append({"source": source, "subdir": subdir, "ref": ref, "names": names})
    _save_sources(sources)


def sync_skills() -> dict[str, list[str]]:
    """Re-run every recorded import, pulling each source's current upstream state.

    For a git repo this re-clones at ``--depth 1``, so it always picks up
    whatever is at the tip of the recorded ``ref`` (or the default branch).
    Returns ``{source: [imported skill names]}``.
    """
    imported: dict[str, list[str]] = {}
    for entry in _load_sources():
        imported[entry["source"]] = import_skills(
            entry["source"],
            subdir=entry.get("subdir", ""),
            names=entry.get("names"),
            ref=entry.get("ref"),
            track=False,  # already recorded; avoid rewriting the manifest mid-loop
        )
    return imported


def import_skills_from_dir(src_dir: str | Path, names: list[str] | None = None) -> list[str]:
    """Copy skill directories from a local folder into ``lab/skills/``."""
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
    track: bool = True,
) -> list[str]:
    """Import skills from a git repo URL or a local folder.

    - Repo (URL ends with .git, has ``://``, or starts with ``git@``): clone,
      then read ``subdir`` (or the repo root).
    - Local folder: read ``source/subdir`` (or ``source``).

    Picks up ``<name>/SKILL.md`` directories per the Agent Skills standard, or a
    single skill whose ``SKILL.md`` sits at the source root. Returns the
    imported skill names.

    When ``track`` is true (the default), the call is recorded in
    ``lab/skills/sources.json`` so a later ``sync_skills()`` (or
    ``python -m lab.core.skills --sync``) can re-import it and pick up
    whatever changed upstream. Pass ``track=False`` for one-off/local imports
    you don't want remembered.
    """
    if _is_repo(source):
        imported = import_skills_from_repo(source, subdir=subdir, names=names, ref=ref)
    else:
        base = Path(source).expanduser()
        if subdir:
            base = base / subdir
        imported = import_skills_from_dir(base, names=names)
    if track:
        _record_source(source, subdir, ref, names)
    return imported


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m lab.core.skills",
        description="Import skills into lab/skills/ from a git repo or a local folder.",
    )
    ap.add_argument(
        "source", nargs="?", help="git repo URL, or a local folder path (omit with --sync)"
    )
    ap.add_argument("--subdir", default="", help="folder within the repo/source to read from")
    ap.add_argument("--names", nargs="*", help="only import these skill names (without .md)")
    ap.add_argument("--ref", help="git branch/tag when source is a repo")
    ap.add_argument(
        "--no-track",
        action="store_true",
        help="don't record this import in lab/skills/sources.json for future --sync runs",
    )
    ap.add_argument(
        "--sync",
        action="store_true",
        help="re-import every source recorded in lab/skills/sources.json, picking up upstream updates",
    )
    args = ap.parse_args()

    if args.sync:
        for source, names in sync_skills().items():
            listing = ", ".join(names) if names else "(none matched)"
            print(f"synced {source}: {listing}")
        return

    if not args.source:
        ap.error("source is required unless --sync is given")

    imported = import_skills(
        args.source, subdir=args.subdir, names=args.names, ref=args.ref, track=not args.no_track
    )
    listing = ", ".join(imported) if imported else "(none matched)"
    print(f"imported {len(imported)} skill(s) into {SKILLS_DIR}: {listing}")


if __name__ == "__main__":
    main()
