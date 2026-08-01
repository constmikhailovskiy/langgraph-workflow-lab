"""Deterministic DRY_RUN outputs for the estimation workflow.

Lets the whole fan-out (planner -> 4 estimates -> summary) run in Studio with
no API key.
"""

# Canonical implementing sides.
SIDES = ["backend", "frontend", "qa", "devops"]

STORIES = [
    {
        "id": "S1",
        "title": "User can submit a feature request via a form",
        "acceptance_criteria": "Form validates input and persists the request.",
    },
    {
        "id": "S2",
        "title": "Requests are listed with status",
        "acceptance_criteria": "List paginates and shows status per request.",
    },
]

# Fixed per-side hours used in DRY_RUN, keyed by side.
_FIXTURE_HOURS = {"backend": 24.0, "frontend": 16.0, "qa": 8.0, "devops": 6.0}


def estimate_for(side: str, stories: list) -> dict:
    """A deterministic per-side estimate for DRY_RUN."""
    hours = _FIXTURE_HOURS.get(side, 8.0)
    n = max(len(stories), 1)
    breakdown = [
        {"story": s.get("id", f"S{i+1}"), "hours": round(hours / n, 1)}
        for i, s in enumerate(stories)
    ]
    return {"hours": hours, "included": True, "breakdown": breakdown}
