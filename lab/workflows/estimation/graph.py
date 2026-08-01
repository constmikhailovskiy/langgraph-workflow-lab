"""Estimation workflow wiring.

    __start__ -> estimate_orchestrator -> brief_prd_input -> story_planner
              -> [be_estimate, frontend_estimate, qa_estimate, devops_estimate]  (parallel)
              -> estimate_summary -> __end__

The four estimate nodes fan out from story_planner and fan in to
estimate_summary; LangGraph runs them concurrently and waits for all four before
the summary. Each writes its own `estimates[<side>]` key via the merge reducer.

Registered in langgraph.json as the graph id "estimation".
"""

from __future__ import annotations

from typing import Annotated

from langgraph.graph import END, START, StateGraph

from lab.core.state import WorkflowState, merge
from lab.workflows.estimation import nodes

ESTIMATE_NODES = ["be_estimate", "frontend_estimate", "qa_estimate", "devops_estimate"]


class EstimationState(WorkflowState, total=False):
    unit: str                       # estimation unit, default "hours"
    sides: list[str]                # implementing sides selected by the orchestrator
    brief: str                      # normalized brief/PRD
    stories: list[dict]             # planned stories
    estimates: Annotated[dict, merge]  # side -> {hours, included, breakdown}
    summary: dict                   # totals + risk buffer + text
    skills_used: Annotated[dict, merge]  # node -> [skill names attached to its prompt]


def build_graph():
    builder = StateGraph(EstimationState)

    builder.add_node("estimate_orchestrator", nodes.estimate_orchestrator)
    builder.add_node("brief_prd_input", nodes.brief_prd_input)
    builder.add_node("story_planner", nodes.story_planner)
    builder.add_node("be_estimate", nodes.be_estimate)
    builder.add_node("frontend_estimate", nodes.frontend_estimate)
    builder.add_node("qa_estimate", nodes.qa_estimate)
    builder.add_node("devops_estimate", nodes.devops_estimate)
    builder.add_node("estimate_summary", nodes.estimate_summary)

    builder.add_edge(START, "estimate_orchestrator")
    builder.add_edge("estimate_orchestrator", "brief_prd_input")
    builder.add_edge("brief_prd_input", "story_planner")

    # fan-out to the four estimates, fan-in to the summary
    for node in ESTIMATE_NODES:
        builder.add_edge("story_planner", node)
        builder.add_edge(node, "estimate_summary")

    builder.add_edge("estimate_summary", END)
    return builder.compile()


graph = build_graph()
