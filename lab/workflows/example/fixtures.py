"""Deterministic DRY_RUN outputs for the example workflow.

Every LLM node has a fixture so the graph runs in Studio with no API key.
"""

SUMMARY = (
    "DRY_RUN fixture summary: the input describes a topic in a few sentences, "
    "condensed here to demonstrate the summarize node without calling a model."
)

CRITIQUE = (
    "DRY_RUN fixture critique: add one concrete example so the summary is less "
    "abstract and easier for a reader to act on."
)
