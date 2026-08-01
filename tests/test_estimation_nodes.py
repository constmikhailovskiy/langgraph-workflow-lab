from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from lab.workflows.estimation import nodes


def _real_settings() -> SimpleNamespace:
    return SimpleNamespace(dry_run=False)


def test_every_estimation_node_calls_local_claude_in_real_mode() -> None:
    responses = iter(
        [
            '["backend", "frontend", "qa", "devops"]',
            "Normalized feature brief",
            '[{"id":"S1","title":"Build it","acceptance_criteria":"It works"}]',
            '{"total":8,"breakdown":[{"story":"S1","hours":8}]}',
            '{"total":5,"breakdown":[{"story":"S1","hours":5}]}',
            '{"total":3,"breakdown":[{"story":"S1","hours":3}]}',
            '{"total":2,"breakdown":[{"story":"S1","hours":2}]}',
            "Estimate: 20 hours before risk buffer, 23 hours total.",
        ]
    )

    with (
        patch.object(nodes, "settings", _real_settings()),
        patch.object(nodes, "claude_print", side_effect=lambda *_: next(responses)) as cli,
    ):
        orchestrated = nodes.estimate_orchestrator({"input": "Feature"})
        brief = nodes.brief_prd_input({"input": " Feature "})
        planned = nodes.story_planner({"brief": brief["brief"]})
        state = {
            "sides": orchestrated["sides"],
            "stories": planned["stories"],
            "unit": "hours",
        }
        estimates = {}
        for fn in (
            nodes.be_estimate,
            nodes.frontend_estimate,
            nodes.qa_estimate,
            nodes.devops_estimate,
        ):
            estimates.update(fn(state)["estimates"])
        summary = nodes.estimate_summary({"unit": "hours", "estimates": estimates})

    assert cli.call_count == 8
    assert [call.args[0] for call in cli.call_args_list] == [
        "estimate_orchestrator",
        "brief_prd_input",
        "story_planner",
        "be_estimate",
        "frontend_estimate",
        "qa_estimate",
        "devops_estimate",
        "estimate_summary",
    ]
    assert summary["summary"]["text"].startswith("Estimate: 20 hours")


def test_unselected_estimate_node_still_calls_claude() -> None:
    with (
        patch.object(nodes, "settings", _real_settings()),
        patch.object(nodes, "claude_print", return_value='{"total":0,"breakdown":[]}') as cli,
    ):
        result = nodes.frontend_estimate(
            {"sides": ["backend"], "stories": [], "unit": "hours"}
        )

    cli.assert_called_once()
    assert result["estimates"]["frontend"]["included"] is False

