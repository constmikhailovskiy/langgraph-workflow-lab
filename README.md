# langgraph-workflow-lab

An extensible, domain-agnostic LangGraph template for building and testing
agentic workflows quickly — the reusable patterns from a mundiir-style SDLC
pipeline (StateGraph + node functions + routing, DRY_RUN fixtures, pluggable
gates, a repair subgraph) with the Go/codegen specifics stripped out.

## Setup

```bash
uv sync
cp .env.example .env    # optional: add ANTHROPIC_API_KEY for real runs
uv run langgraph dev
```

Studio opens with the `estimation` graph (feature brief in, per-side effort
estimate out). `DRY_RUN=false` (the default) runs every node through the
local `claude` CLI under the host session — no API key needed. Set
`DRY_RUN=true` in `.env` to walk the graph on fixtures instead.

## Running from the console

You don't need Studio to run a graph — invoke it directly as a Python script.
Unlike `langgraph dev`, a plain `uv run` does **not** read `.env` on its own,
so pass `--env-file .env` explicitly:

```bash
uv run --env-file .env python -c "
from lab.workflows.estimation.graph import graph
result = graph.invoke({'input': 'Add a dark mode toggle to settings.'})
print(result['summary']['text'])
"
```

Override a single run without touching `.env` by exporting the var instead,
e.g. `DRY_RUN=true uv run python -c "..."` to walk the graph on fixtures
without spending any `claude -p` sessions (an exported env var wins over
`--env-file`, so you can drop `--env-file` too in this case). The full state
(`sides`, `stories`, `estimates`, `summary`, `log`) is in `result`, not just
the printed summary text.

To run the test suite from the console:

```bash
uv run --with pytest pytest tests/ -v
```

## Layout

```
lab/
├── core/                 # reusable, domain-free batteries
│   ├── state.py          # WorkflowState base (subclass + add your fields)
│   ├── settings.py       # DRY_RUN flag + per-node model map
│   ├── failures.py       # FailureKind + is_failed()
│   ├── llm.py            # llm_for(node) -> chat model (langchain path)
│   ├── claude_cli.py     # claude_print(node, prompt) -> local `claude -p` under the host session
│   ├── gates.py          # Gate abstraction (opt-in validation)
│   ├── repair.py         # generic repair subgraph (opt-in)
│   └── tools/fs.py       # sandboxed read/write (both guarded)
├── skills/                # Agent Skills (agentskills.io) injected into node prompts (see below)
└── workflows/
    └── estimation/       # worked reference: copy me to start a new workflow
        ├── graph.py      # StateGraph wiring
        ├── nodes.py      # node functions
        └── fixtures.py   # DRY_RUN outputs
```

## Skills

Skills follow the open [Agent Skills](https://agentskills.io) standard: each
one is a directory `lab/skills/<name>/SKILL.md` (frontmatter + instructions,
plus optional `scripts/`/`references/`/`assets/`), the same format Claude Code
and other agentskills.io-compatible clients use. Each real (non-DRY_RUN) node
in the estimation workflow attaches its own skill via `with_skills`, so its
rubric lives in one reusable, swappable folder instead of being baked into the
prompt string:

| Node               | Skill                  |
| ------------------ | ----------------------- |
| `estimate_orchestrator` | `side-selection`     |
| `brief_prd_input`  | `brief-normalization`    |
| `story_planner`    | `story-decomposition`   |
| `be_estimate`      | `backend-estimation`     |
| `frontend_estimate`| `frontend-estimation`    |
| `qa_estimate`      | `qa-estimation`          |
| `devops_estimate`  | `devops-estimation`      |
| `estimate_summary` | `estimate-summary`      |

See `lab/skills/README.md` for how the skill layer works and how to import
skills from another repo.

## Adding a workflow

Copy `lab/workflows/estimation/` to `lab/workflows/<name>/`, edit the nodes and
wiring, and register it in `langgraph.json` under `graphs`. Or use the global
`build-langgraph-workflow` skill: give it a node chain like
`analyze_prd -> decompose_into_tasks -> generate_api_contract` and it scaffolds
the runnable workflow for you.

## Node kinds

`llm_step` · `transform` · `gate` · `human_review` · `router` · `subagent`.
The estimation workflow's nodes are `llm_step`s calling `claude_print`; the
other kinds plug into the same core.
