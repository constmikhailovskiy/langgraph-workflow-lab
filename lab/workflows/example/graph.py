"""Example workflow wiring: __start__ -> summarize -> critique -> __end__.

Registered in langgraph.json as the graph id "example". Copy this package to
lab/workflows/<name>/ to start a new workflow (the skill automates that).
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from lab.core.state import WorkflowState
from lab.workflows.example import nodes


class ExampleState(WorkflowState, total=False):
    summary: str
    critique: str


def build_graph():
    builder = StateGraph(ExampleState)
    builder.add_node("summarize", nodes.summarize)
    builder.add_node("critique", nodes.critique)

    builder.add_edge(START, "summarize")
    builder.add_edge("summarize", "critique")
    builder.add_edge("critique", END)
    return builder.compile()


graph = build_graph()
