# lab/skills

Reusable **skills** for LLM nodes and subagents, in the open
[Agent Skills](https://agentskills.io) format. Each skill is a directory:

```
lab/skills/<name>/
├── SKILL.md          # required: YAML frontmatter (name, description, ...) + instructions
├── scripts/           # optional: executable code
├── references/        # optional: additional docs the instructions can point to
└── assets/             # optional: templates, resources
```

`SKILL.md`'s body (frontmatter stripped) is injected into a node's prompt via
`lab.core.skills.with_skills`:

```python
from lab.core.skills import with_skills
prompt = with_skills(base_prompt, ["critique-checklist"])   # -> base + "# Skills" + body
```

This is the same mechanism Claude Code and other
[agentskills.io-compatible clients](https://agentskills.io/clients) use to load
skills — a versioned instruction folder you attach to any `llm_step` or
`subagent` node, rather than re-writing the same guidance in every prompt.

Add a skill by creating `lab/skills/<name>/SKILL.md` (`name` in the frontmatter
must match the directory name — lowercase, hyphens only, no leading/trailing or
doubled hyphen; see the [spec](https://agentskills.io/specification) for the
full frontmatter rules) and attaching it per node (the
`build-langgraph-workflow` skill asks "any skills to attach?" per LLM node).

## Importing skills from another repo or folder

Pull curated, agentskills.io-compatible skills in instead of hand-writing them.
Copies each matched skill's whole directory — `SKILL.md` plus any bundled
`scripts/`, `references/`, `assets/`.

```bash
# from a git repo of skills (each top-level folder is a skill)
uv run python -m lab.core.skills https://github.com/org/skills.git

# from a specific subfolder of a repo, only some skills, on a branch
uv run python -m lab.core.skills https://github.com/org/monorepo.git \
    --subdir agents/skills --names review-checklist api-conventions --ref main

# from a local folder / a subfolder of a repo on disk
uv run python -m lab.core.skills /path/to/repo --subdir prompts
```

Or programmatically:

```python
from lab.core.skills import import_skills
import_skills("https://github.com/org/skills.git", subdir="agents/skills")
```

Imported skills land in `lab/skills/<name>/` and are immediately attachable by
name.

**Real example** — every skill the estimation workflow's nodes attach (see
`NODE_SKILLS` in `lab/workflows/estimation/nodes.py`) was pulled whole from a
real marketplace repo, no `--names` filter, so future skills that repo adds
land here too on the next `--sync`:

```bash
uv run python -m lab.core.skills https://github.com/constmikhailovskiy/htbs-2-02-skills.git \
    --subdir skills
```

## Keeping imported skills up to date

Every `import_skills(...)` call — CLI or programmatic — is recorded in
`lab/skills/sources.json` (unless you pass `--no-track` / `track=False`):

```json
{"source": "https://...git", "subdir": "skills", "ref": null, "names": null}
```

`names: null` means "whatever's in `subdir` at sync time" — no need to
re-list names as the upstream repo grows.

Re-run every recorded import to pick up whatever changed upstream:

```bash
uv run python -m lab.core.skills --sync
```

This re-clones each recorded repo at `--depth 1` (so it always gets the tip of
the recorded `ref`, or the default branch) and overwrites the local copy — the
same mechanism a plugin-update button would use. Importing the same
`(source, subdir, ref)` again — whether by hand or via `--sync` — updates the
existing manifest entry rather than duplicating it.
