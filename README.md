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

Studio opens with the `example` graph (`summarize -> critique`). `DRY_RUN=true`
(the default) makes it run with no API key — every node returns a fixture.
Set `DRY_RUN=false` in `.env` for real model calls.

## Layout

```
lab/
├── core/                 # reusable, domain-free batteries
│   ├── state.py          # WorkflowState base (subclass + add your fields)
│   ├── settings.py       # DRY_RUN flag + per-node model map
│   ├── failures.py       # FailureKind + is_failed()
│   ├── llm.py            # llm_for(node) -> chat model
│   ├── gates.py          # Gate abstraction (opt-in validation)
│   ├── repair.py         # generic repair subgraph (opt-in)
│   └── tools/fs.py       # sandboxed read/write (both guarded)
└── workflows/
    └── example/          # worked reference: copy me to start a new workflow
        ├── graph.py      # StateGraph wiring
        ├── nodes.py      # node functions
        └── fixtures.py   # DRY_RUN outputs
```

## Adding a workflow

Copy `lab/workflows/example/` to `lab/workflows/<name>/`, edit the nodes and
wiring, and register it in `langgraph.json` under `graphs`. Or use the global
`build-langgraph-workflow` skill: give it a node chain like
`analyze_prd -> decompose_into_tasks -> generate_api_contract` and it scaffolds
the runnable workflow for you.

## Node kinds

`llm_step` · `transform` · `gate` · `human_review` · `router` · `subagent`.
The example uses two `llm_step`s; the other kinds plug into the same core.
