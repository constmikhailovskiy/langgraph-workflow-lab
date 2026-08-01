# Estimation determinism report

- iterations per input: **4**
- mode: **REAL (live LLM)**
- headline metric: coefficient of variation (CV = stdev / mean) of the grand total

## Harness: `langgraph`

### Input: `offline_workouts` · 2 run error(s)

**Grand total (hours):** mean 154.47, range 126.5–185.1 (Δ 58.6), stdev 29.391, **CV 0.1903 → variable (15-30% CV)**

| side | mean | min | max | Δ range | stdev | CV | verdict |
|---|---|---|---|---|---|---|---|
| backend | 49.33 | 42.0 | 54.0 | 12.0 | 6.429 | 0.1303 | moderately stable (5-15% CV) |
| frontend | 9.33 | 0.0 | 28.0 | 28.0 | 16.166 | 1.7321 | highly variable (>30% CV) |
| qa | 75.67 | 68.0 | 80.0 | 12.0 | 6.658 | 0.088 | moderately stable (5-15% CV) |
| devops | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | deterministic (0% CV) |

- side-selection stability: **1 distinct set(s)** — {'backend,frontend,qa': 3}
- stories/run: mean 8.0, range 7.0–9.0

## Harness: `raw`

### Input: `offline_workouts` · 1 run error(s)

**Grand total (hours):** mean 171.93, range 156.4–209.3 (Δ 52.9), stdev 25.081, **CV 0.1459 → moderately stable (5-15% CV)**

| side | mean | min | max | Δ range | stdev | CV | verdict |
|---|---|---|---|---|---|---|---|
| backend | 37.0 | 0.0 | 54.0 | 54.0 | 25.534 | 0.6901 | highly variable (>30% CV) |
| frontend | 27.75 | 0.0 | 71.0 | 71.0 | 34.452 | 1.2415 | highly variable (>30% CV) |
| qa | 84.75 | 71.0 | 96.0 | 25.0 | 10.436 | 0.1231 | moderately stable (5-15% CV) |
| devops | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | deterministic (0% CV) |

- side-selection stability: **1 distinct set(s)** — {'backend,frontend,qa': 4}
- stories/run: mean 8.0, range 8.0–8.0
