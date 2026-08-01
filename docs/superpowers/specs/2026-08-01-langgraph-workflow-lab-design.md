# Design: langgraph-workflow-lab + build-langgraph-workflow skill

**Date:** 2026-08-01
**Status:** Awaiting user review

## Purpose

A reusable, domain-agnostic LangGraph template ("workflow lab") plus a global
Claude Code skill that scaffolds new agentic workflows from a node-chain the user
writes (e.g. `analyze_prd -> decompose_into_tasks -> generate_api_contract`). The
goal is to spin up and test multi-node agentic workflows in LangGraph Studio
quickly, at or above the structural sophistication of the mundiir
`htbs-2-practice-1` project — but without its Go/codegen specifics.

Two deliverables:
1. **`langgraph-workflow-lab`** — the extensible template project.
2. **`build-langgraph-workflow`** — a global skill (`~/.claude/skills/`) that
   generates workflows into any lab project.

## Non-goals (YAGNI)

- No Go code generation, `make` gates, `sqlc`/`oapi-codegen`, or compile loops
  (mundiir-specific; explicitly stripped).
- No runtime "meta-agent" that builds graphs at execution time. Generation is
  done by Claude in-session via the skill, emitting plain `.py` files.
- No visual/no-code graph editor. Nodes and topology are always Python code;
  LangGraph Studio remains view/run/trace only.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Template core | Agnostic workflow lab — keep patterns, strip Go/codegen |
| Skill home | Global `~/.claude/skills/build-langgraph-workflow` |
| Generation strategy | Runnable-by-default (working nodes + fixtures, ask only on gaps/insertion) |
| Template name/location | `/Users/konstie/StudioProjects/langgraph-workflow-lab` |
| Default model | `claude-opus-4-8` (Opus), overridable per node via `MODEL_*` |
| DRY_RUN | Default `true` — free topology walks with no API key |

## Component 1 — The template project

Clean clone of mundiir's *architecture*, not its content.

```
langgraph-workflow-lab/
├── pyproject.toml          # langgraph, langchain, langchain-anthropic,
│                           # python-dotenv; dev: langgraph-cli[inmem]
├── langgraph.json          # graphs: { "example": "./lab/workflows/example/graph.py:graph" }
│                           # env: ".env"
├── .env.example            # ANTHROPIC_API_KEY, DRY_RUN=true,
│                           # MODEL_REASONING=claude-opus-4-8, MODEL_CODEGEN=claude-opus-4-8
├── README.md
├── lab/
│   ├── __init__.py
│   ├── core/               # domain-free reusable batteries
│   │   ├── state.py        # base WorkflowState TypedDict: messages, log (append reducer),
│   │   │                   #   failure_kind, raw_output, plus free-form artifact fields
│   │   ├── settings.py     # DRY_RUN flag, per-node model map, repair budget/timeouts
│   │   ├── failures.py     # FailureKind enum + classify(output) -> FailureKind
│   │   ├── llm.py          # llm_for(node): init_chat_model honoring settings; DRY_RUN short-circuit
│   │   ├── gates.py        # Gate abstraction: a named check -> GateResult(ok, failure_kind, summary)
│   │   ├── repair.py       # reusable repair subgraph (read_source guarded — mundiir bug fixed)
│   │   └── tools/
│   │       ├── __init__.py
│   │       └── fs.py       # optional sandboxed file read/write (generic; configurable roots)
│   └── workflows/
│       ├── __init__.py
│       └── example/        # ONE minimal worked example (2–3 nodes) that runs in Studio
│           ├── __init__.py
│           ├── graph.py    # StateGraph wiring + route_after_* funcs
│           ├── nodes.py    # node functions (1 llm_step + 1 transform, say)
│           └── fixtures.py # DRY_RUN fixtures so it runs with no key
└── docs/
    └── superpowers/specs/  # this design doc
```

### Core design principles carried over from mundiir
- **Node = pure-ish function** `(state) -> partial_state_dict`, registered via
  `builder.add_node(name, fn)`. Topology and routing live in `graph.py`.
- **DRY_RUN fixtures**: every LLM/side-effecting node has a deterministic dry-run
  path so a workflow is walkable in Studio with no key and no external tools.
- **Pluggable gates + repair**: `gates.py` defines a generic check contract; a
  gate failure sets `failure_kind` and routing sends control to the reusable
  `repair` subgraph. Repair is *optional* per workflow — the skill wires it only
  when a workflow declares a gate.
- **Per-node model map** in `settings.py` so swapping models never edits a graph.

### The example workflow (worked reference)
A trivial 2–3 node graph — e.g. `summarize -> critique` — with one `llm_step`
and one `transform`, plus DRY_RUN fixtures. Serves as the copy-me example the
skill (and the user) imitate. It must run in Studio out of the box in DRY_RUN.

## Component 2 — The `build-langgraph-workflow` skill

Global skill in `~/.claude/skills/build-langgraph-workflow/SKILL.md`, authored
via `superpowers:writing-skills`.

### Invocation
`/build-langgraph-workflow analyze_prd -> decompose_into_tasks -> generate_api_contract`
(chain may also be given/edited interactively). Runs against the current lab
project (detected by `langgraph.json` + `lab/` layout).

### Node-kind taxonomy (first-class "different agent structure")
The skill classifies each node into one kind, inferring from the name/verb and
confirming when ambiguous:

| Kind | What it emits |
|---|---|
| `llm_step` | model call via `core.llm.llm_for(node)` with a generated prompt; reads/writes named state fields |
| `transform` | deterministic pure function, no model |
| `gate` | runs a check via `core.gates`; sets `failure_kind`; routes to repair/next |
| `human_review` | `interrupt()` checkpoint; resumes on approve/feedback |
| `router` | conditional branch function selecting the next node |
| `subagent` | nested subgraph or `create_agent` with tools (e.g. a repair/loop) |

### Behavior (runnable-by-default)
1. **Parse** the chain into ordered nodes; assign a kind + a **one-line
   explanation** to each; present the list.
2. For any node whose behavior can't be confidently inferred, **ask the user
   one question at a time** (what it consumes, what it produces, its rule/prompt).
3. **Generate real Python**: for each node a working function (LLM nodes get a
   generated prompt + `llm_for`; deterministic nodes get real logic) **and** a
   DRY_RUN fixture, plus `graph.py` wiring and `route_after_*` where branching is
   needed. Write into a new package `lab/workflows/<name>/` and **register it in
   `langgraph.json`**.
4. **Node insertion**: when the user adds a node mid-chain without specifying
   behavior, the skill **asks about its neighbors** — what it receives from the
   predecessor and what the successor needs — plus its purpose, then generates it
   and re-wires the edges.
5. **State fields**: inferred from the data each node consumes/produces, added to
   the workflow's state TypedDict (extends `core.state.WorkflowState`).
6. **Finish** by printing exactly how to test: `cd <lab> && uv run langgraph dev`,
   select the new graph, DRY_RUN walk, then `DRY_RUN=false` for a real run.

### Explanations
For each generated node the skill writes a short docstring + a one-line summary
in the run output ("`decompose_into_tasks`: LLM step — reads `prd`, emits a list
of `tasks` with id/title/acceptance-criteria"). This satisfies "explain each step
briefly."

## Data flow (example: the user's PRD chain)

```
brief/prd (input)
  → analyze_prd     (llm_step: prd -> structured requirements)
  → decompose_into_tasks (llm_step: requirements -> tasks[])
  → generate_api_contract (llm_step or transform: tasks -> openapi/contract)
  → END
```
Each arrow is a plain `add_edge`; branches become `add_conditional_edges` with a
generated `route_after_*`. Gates/human-review/repair are inserted only where the
node kinds call for them.

## Error handling
- **DRY_RUN** guarantees every node has a no-key path; a workflow always runs in
  Studio even before real logic is exercised.
- **Sandbox reads/writes** (`core.tools.fs`) catch out-of-root access and return a
  recoverable error string (the mundiir `read_source` crash is fixed here from the
  start — reads and writes both guarded).
- **Repair subgraph** is opt-in per workflow; when present, a gate failure routes
  to a bounded repair loop (budget + no-progress detection carried from mundiir).
- **Skill-time validation**: after generating, the skill imports the new
  `graph.py` (syntax/topology check) and reports failure clearly rather than
  leaving a broken graph.

## Testing strategy
- **Template**: the `example` workflow must `import` and run in Studio in DRY_RUN;
  a smoke test asserts the compiled graph exposes the expected nodes.
- **Skill**: dogfood by generating the user's `analyze_prd -> decompose_into_tasks
  -> generate_api_contract` workflow, then (a) DRY_RUN walk in Studio, (b) confirm
  `langgraph.json` registration, (c) optional real run with the Anthropic key.
- Free-by-default: DRY_RUN fixtures mean topology/routing is testable without
  spending tokens; real runs are an explicit flip.

## Open questions / assumptions
- Assumes `uv` for the lab project (consistent with your other projects).
- Assumes the skill targets one lab project at a time, detected via `langgraph.json`.
- The `example` workflow's concrete nodes (`summarize -> critique`) are a
  placeholder; can be swapped during implementation if you prefer a different
  trivial example.

## Build order
1. Scaffold `langgraph-workflow-lab` (core + example workflow), verify it runs in
   Studio (DRY_RUN).
2. Author the global `build-langgraph-workflow` skill via `writing-skills`.
3. Dogfood: generate the PRD chain workflow with the skill and test it.
