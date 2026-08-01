# eval — estimation determinism framework

Measures how deterministic the estimation result is for the **same input**: runs a
harness N times, then reports the spread (range, stdev, and CV = stdev/mean) of the
grand total, each side, side-selection, and story count. Reports are the evidence.

## Harnesses (same metrics, comparable)

- `harness_langgraph` — runs the estimation via the **LangGraph** graph.
- `harness_raw_skills` — replays the **raw skills** (from `lab/skills/`, sourced
  from the `htbs-2-02-skills` repo) as plain sequential LLM calls, no graph.

## Run

```bash
cd /Users/konstie/StudioProjects/langgraph-workflow-lab

# Smoke test — no tokens; DRY_RUN fixtures are deterministic so every CV is 0.
DRY_RUN=true uv run python -m eval.run_eval --iterations 3

# Real determinism eval — spends Anthropic tokens (needs ANTHROPIC_API_KEY).
DRY_RUN=false uv run python -m eval.run_eval --iterations 7 --harness both
```

Flags: `--iterations N`, `--harness {langgraph,raw,both}`, `--input {name,all}`.
Inputs are fixed in `eval/inputs/sample_briefs.py` (stable, so reports compare).

## Output

`eval/reports/<timestamp>/report.md` (human evidence) + `raw.json` (every run's
numbers). CV verdict bands: 0 deterministic · <5% highly stable · 5–15% moderate ·
15–30% variable · >30% highly variable.

## Notes

- The real eval only measures variance with live LLM calls; DRY_RUN is for
  validating the harness, not for determinism claims.
- The raw-skills harness reflects the imported skills — import them first
  (`python -m lab.core.skills <repo>`) so both harnesses use the same prompts.
- Risk buffer (`ESTIMATION_RISK_BUFFER_PCT`) is applied identically in both, so it
  never contributes to the delta.
