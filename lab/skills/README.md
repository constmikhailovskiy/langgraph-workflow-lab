# lab/skills

Reusable markdown **skills** for LLM nodes and subagents. Each `<name>.md` file's
body is injected into a node's prompt via `lab.core.skills.with_skills`.

```python
from lab.core.skills import with_skills
prompt = with_skills(base_prompt, ["critique-checklist"])   # -> base + "# Skills" + body
```

This is the LangGraph-native analog of a Claude Code skill: a versioned
instruction you attach to any `llm_step` or `subagent` node, rather than
re-writing the same guidance in every prompt. Optional `---` frontmatter is
stripped; only the instruction body is injected.

Add a skill by dropping a markdown file here; attach it per node (the
`build-langgraph-workflow` skill asks "any skills to attach?" per LLM node).

## Importing skills from another repo or folder

Pull curated skills in instead of hand-writing them. Handles flat `<name>.md`
and Claude-Code-style `<name>/SKILL.md` layouts.

```bash
# from a git repo of skills
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

Imported files land here in `lab/skills/` and are immediately attachable.

