# Estimation determinism report

- iterations per input: **4**
- mode: **REAL (live LLM)**
- headline metric: coefficient of variation (CV = stdev / mean) of the grand total

## Harness: `langgraph`

### Input: `offline_workouts` · 1 run error(s)

**Grand total (hours):** mean 162.7, range 126.5–187.4 (Δ 60.9), stdev 29.104, **CV 0.1789 → variable (15-30% CV)**

| side | mean | min | max | Δ range | stdev | CV | verdict |
|---|---|---|---|---|---|---|---|
| backend | 51.0 | 42.0 | 56.0 | 14.0 | 6.218 | 0.1219 | moderately stable (5-15% CV) |
| frontend | 14.75 | 0.0 | 31.0 | 31.0 | 17.076 | 1.1577 | highly variable (>30% CV) |
| qa | 75.75 | 68.0 | 80.0 | 12.0 | 5.439 | 0.0718 | moderately stable (5-15% CV) |
| devops | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | deterministic (0% CV) |

- side-selection stability: **1 distinct set(s)** — {'backend,frontend,qa': 4}
- stories/run: mean 7.75, range 7.0–9.0

**Per-iteration results (hours)** — `ok` rows are the 4 valid samples the stats above use; `excluded` = degenerate/rate-limited (no stories or total 0), not counted:

| # | status | sides | stories | backend | frontend | qa | devops | total |
|---|---|---|---|---|---|---|---|---|
| 1 | ok | backend,frontend,qa | 7 | 54 | 28 | 79 | – | 185.1 |
| 2 | ok | backend,frontend,qa | 9 | 42 | 0 | 68 | – | 126.5 |
| 3 | ok | backend,frontend,qa | 8 | 52 | 0 | 80 | – | 151.8 |
| 4 | ok | backend,frontend,qa | 7 | 56 | 31 | 76 | – | 187.4 |
| 5 | excluded | backend,frontend,qa | 0 | 0 | 0 | 0 | – | 0.0 |

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

**Per-iteration results (hours)** — `ok` rows are the 4 valid samples the stats above use; `excluded` = degenerate/rate-limited (no stories or total 0), not counted:

| # | status | sides | stories | backend | frontend | qa | devops | total |
|---|---|---|---|---|---|---|---|---|
| 1 | ok | backend,frontend,qa | 8 | 54 | 0 | 88 | 0 | 163.3 |
| 2 | ok | backend,frontend,qa | 8 | 0 | 40 | 96 | 0 | 156.4 |
| 3 | ok | backend,frontend,qa | 8 | 54 | 0 | 84 | 0 | 158.7 |
| 4 | excluded | backend,frontend,qa | 0 | 0 | 0 | 0 | 0 | 0.0 |
| 5 | ok | backend,frontend,qa | 8 | 40 | 71 | 71 | 0 | 209.3 |
