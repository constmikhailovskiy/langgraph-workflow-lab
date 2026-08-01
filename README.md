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

The node/skill mapping is `NODE_SKILLS` in `lab/workflows/estimation/nodes.py`
— a single dict every node reads from (no node inlines a skill name of its
own), so the wiring is deterministic and grep-able in one place:

| Node               | Skill                  |
| ------------------- | ----------------------- |
| `estimate_orchestrator` | `estimate-orchestrator` |
| `brief_prd_input`  | `brief-prd-input`        |
| `story_planner`    | `story-planner-hitl`     |
| `be_estimate`      | `be-estimate`            |
| `frontend_estimate`| `frontend-estimate`      |
| `qa_estimate`      | `qa-estimate`            |
| `devops_estimate`  | `devops-estimate`        |
| `estimate_summary` | `estimate-summary`      |

All eight are imported from the
[`estimator` plugin](https://github.com/constmikhailovskiy/htbs-2-02-skills) —
a real agentskills.io-style marketplace repo, not hand-written. Seven match
that repo's own `ORCHESTRATION.md` node names exactly; `story_planner` is a
deliberate override — the source repo's graph runs the thinner `story-planner`
placeholder, this workflow runs the fuller `story-planner-hitl` instead.
`tests/test_estimation_nodes.py::test_node_skills_mapping_is_deterministic_and_matches_available_skills`
asserts `NODE_SKILLS` covers exactly these eight nodes and every mapped skill
exists under `lab/skills/`.

`wbs` and `story-planner` were imported too but aren't wired to any node: the
source repo's own docs mark `wbs` "not in the graph", and `story-planner` is
the placeholder `story-planner-hitl` supersedes here.

**Known open threads, inherited from the source repo, not silently patched
over:**

- Per that repo's own README, only `frontend-estimate` and `wbs` are finished
  (✅); five of the other six are explicitly marked `placeholder` — literal
  `TODO: instructions for the X node` bodies. `frontend-estimate`'s finished
  SKILL.md asks for a three-point (optimistic/likely/pessimistic) per-story
  estimate against the full `contracts/story.v1.md` shape, while this repo's
  `story_planner`/`_estimate`/`estimate_summary` still use the simpler
  `{"total": ..., "breakdown": [...]}` contract — the same shape mismatch
  `ORCHESTRATION.md` documents as unresolved upstream. `--sync` (below) picks
  up the fix once upstream finishes the placeholders and settles the contract.
- `story-planner-hitl` mandates two human-in-the-loop approval gates and
  expects the caller to persist a `decision_log` and resume only on an
  explicit human decision. `story_planner` is a single `claude_print` call
  with no pause/resume mechanism (no `interrupt()`, no checkpointer) —
  honoring the gates for real needs a LangGraph `interrupt()`-based node, a
  bigger change than swapping the attached skill. See the "open threads" note
  in `lab/workflows/estimation/nodes.py`'s module docstring.

See `lab/skills/README.md` for how the skill layer works and how to import
skills from another repo.

**Keeping imported skills up to date:** every `import_skills(...)` call (and
the `python -m lab.core.skills <source> ...` CLI) is recorded in
`lab/skills/sources.json`. Run

```bash
uv run python -m lab.core.skills --sync
```

to re-import every recorded source — this re-clones each repo at `--depth 1`,
so it always picks up whatever is currently at the tip of the recorded ref (or
default branch) and overwrites the local copy. Use `--no-track` on a one-off
import you don't want remembered.

**Proof a node used its skill:** every real node writes to `skills_used[<node>]`
in graph state (dict-merge reducer, alongside `estimates`) — after a run,
`result["skills_used"]` names the exact skill each node attached, independent
of the LLM's reply content. `log` entries also say `skill=<name>` per node for
a human-readable trace. See
`tests/test_estimation_nodes.py::test_full_graph_run_records_which_skill_each_node_used`.

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
