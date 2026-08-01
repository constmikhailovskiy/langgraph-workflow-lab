from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from lab.workflows.estimation import nodes
from lab.workflows.estimation.graph import graph


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


def test_every_node_attaches_its_skill_to_the_prompt() -> None:
    """Each node's prompt must carry its own `# Skills` section, not a shared one."""
    prompts: dict[str, str] = {}

    def _capture(node: str, prompt: str) -> str:
        prompts[node] = prompt
        return {
            "estimate_orchestrator": '["backend"]',
            "brief_prd_input": "Normalized brief",
            "story_planner": '[{"id":"S1","title":"Build it","acceptance_criteria":"It works"}]',
            "be_estimate": '{"total":1,"breakdown":[]}',
            "frontend_estimate": '{"total":1,"breakdown":[]}',
            "qa_estimate": '{"total":1,"breakdown":[]}',
            "devops_estimate": '{"total":1,"breakdown":[]}',
            "estimate_summary": "Summary text",
        }[node]

    with (
        patch.object(nodes, "settings", _real_settings()),
        patch.object(nodes, "claude_print", side_effect=_capture),
    ):
        orchestrated = nodes.estimate_orchestrator({"input": "Feature"})
        nodes.brief_prd_input({"input": "Feature"})
        planned = nodes.story_planner({"brief": "Feature"})
        state = {"sides": orchestrated["sides"], "stories": planned["stories"], "unit": "hours"}
        for fn in (nodes.be_estimate, nodes.frontend_estimate, nodes.qa_estimate, nodes.devops_estimate):
            fn(state)
        nodes.estimate_summary({"unit": "hours", "estimates": {}})

    expected_skill_markers = {
        "estimate_orchestrator": "genuinely needs: backend, frontend, qa, devops",
        "brief_prd_input": "This node is deterministic",
        "story_planner": "without pausing for human approval",
        "be_estimate": "Estimate ONLY backend work",
        "frontend_estimate": "estimating ONLY the frontend (web UI) work",
        "qa_estimate": "Estimate ONLY QA work",
        "devops_estimate": "Estimate ONLY DevOps and infrastructure work",
        "estimate_summary": "This node is arithmetic, not judgment",
    }
    for node, marker in expected_skill_markers.items():
        assert "# Skills" in prompts[node], f"{node} prompt missing a Skills section"
        assert marker in prompts[node], f"{node} prompt missing its expected skill content"


def test_full_graph_run_records_which_skill_each_node_used() -> None:
    """End-to-end proof: after a real graph run, `skills_used` names the exact
    skill each node attached — not just that a `# Skills` section existed."""
    responses = {
        "estimate_orchestrator": '["backend", "frontend", "qa", "devops"]',
        "brief_prd_input": "Normalized feature brief",
        "story_planner": '[{"id":"S1","title":"Build it","acceptance_criteria":"It works"}]',
        "be_estimate": '{"total":8,"breakdown":[{"story":"S1","hours":8}]}',
        "frontend_estimate": '{"total":5,"breakdown":[{"story":"S1","hours":5}]}',
        "qa_estimate": '{"total":3,"breakdown":[{"story":"S1","hours":3}]}',
        "devops_estimate": '{"total":2,"breakdown":[{"story":"S1","hours":2}]}',
        "estimate_summary": "Estimate: 20 hours before risk buffer, 23 hours total.",
    }

    with (
        patch.object(nodes, "settings", _real_settings()),
        patch.object(nodes, "claude_print", side_effect=lambda node, prompt: responses[node]),
    ):
        result = graph.invoke({"input": "Add a dark mode toggle to settings."})

    assert result["skills_used"] == {
        "estimate_orchestrator": ["estimate-orchestrator"],
        "brief_prd_input": ["brief-prd-input"],
        "story_planner": ["story-planner-hitl"],
        "be_estimate": ["be-estimate"],
        "frontend_estimate": ["frontend-estimate"],
        "qa_estimate": ["qa-estimate"],
        "devops_estimate": ["devops-estimate"],
        "estimate_summary": ["estimate-summary"],
    }
    assert result["summary"]["text"].startswith("Estimate: 20 hours")
    assert result["stories"] == [{"id": "S1", "title": "Build it", "acceptance_criteria": "It works"}]


def test_node_skills_mapping_is_deterministic_and_matches_available_skills() -> None:
    """NODE_SKILLS is the single source of truth for node<->skill wiring — this
    guards it from silently drifting out of sync with the graph or lab/skills/."""
    from lab.core import skills as skills_module
    from lab.workflows.estimation.graph import ESTIMATE_NODES

    expected_nodes = {
        "estimate_orchestrator",
        "brief_prd_input",
        "story_planner",
        "estimate_summary",
        *ESTIMATE_NODES,
    }
    assert set(nodes.NODE_SKILLS) == expected_nodes

    available = set(skills_module.available_skills())
    for node, skill in nodes.NODE_SKILLS.items():
        assert skill in available, f"{node} maps to skill {skill!r}, missing from lab/skills/"

