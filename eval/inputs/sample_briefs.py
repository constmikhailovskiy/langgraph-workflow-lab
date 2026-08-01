"""Fixed inputs for determinism evals. Same input in, N runs, measure the spread.

Keep these stable — changing an input invalidates comparison across report runs.
"""

INPUTS = {
    "feature_request_form": {
        "input": (
            "Build a feature-request submission form. Authenticated users submit "
            "requests (title, description, priority). Requests are listed with "
            "status filters and pagination; admins can change status. Send an email "
            "notification when a request's status changes."
        )
    },
    "csv_export": {
        "input": (
            "Add CSV export to the reports page. A user can export the currently "
            "filtered report to CSV, with a progress indicator for large exports and "
            "a download link when the file is ready."
        )
    },
    # Etalon PRD used for the determinism eval evidence run.
    "offline_workouts": {
        "input": """# PRD: Offline workouts and sync

**Owner:** Product · **Draft:** 2026-08-01 · **Calibration:** hidden work — the requirements read
small, the work is not

## Problem

People train in basement gyms, on planes and in parks with no signal. Today the workout player
needs the network for every set it records, so a lost connection loses the session. 8% of started
sessions end with no completion event, and the drop correlates with poor connectivity rather than
with users quitting.

## Goal and Objective

A workout completed without a network connection must be indistinguishable, afterwards, from one
completed online.

- **Objective:** a session can start, run and finish fully offline.
- **Objective:** when connectivity returns, the session appears in history and in stats with no
  user action.

## Success Metrics

| Metric | Now | Target |
|---|---|---|
| Started sessions with no completion event | 8% | < 2% |
| Sessions recovered by sync | — | > 95% of offline sessions |
| Duplicate sessions in history after sync | — | 0 |

## Requirements

| ID | Requirement |
|---|---|
| REQ-001 | Workout content for the next 7 planned days is available on device without network |
| REQ-002 | A session records sets, reps, weight and duration while offline |
| REQ-003 | Completed offline sessions upload automatically once connectivity returns |
| REQ-004 | The same session is never counted twice, however many times sync retries |
| REQ-005 | If the same session was edited on two devices offline, the later completion time wins and the user is told |
| REQ-006 | History and stats screens show a pending-sync state rather than a wrong total |
| REQ-007 | Sessions recorded before this release keep working and are not re-uploaded |
| REQ-008 | On-device workout data does not exceed 200 MB and is evicted oldest-first |

## Happy Path

1. Before flying, the user opens the app on wifi; the next week of workouts downloads.
2. In the air, offline, they open Thursday's workout and complete all six sets.
3. The summary screen appears immediately, marked "will sync".
4. On landing the phone reconnects. Within a minute the session is in history and stats are updated.
5. Nothing is duplicated, and the user never pressed a sync button.

## Scope

**In:** content prefetch, local session storage, background upload with retry, idempotent ingest,
conflict resolution, pending-sync UI, migration of existing local data, cache eviction.

**Out:** offline video streaming, offline access to social feed, editing a synced session,
cross-device live resume, offline sign-in for a brand-new user.
"""
    },
}
