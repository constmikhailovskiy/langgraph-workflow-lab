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
