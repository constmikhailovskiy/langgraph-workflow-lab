"""Model access for LLM nodes.

Nodes call ``llm_for(node)`` to get a chat model configured for that node. The
DRY_RUN short-circuit is intentionally NOT here: each node checks
``settings.dry_run`` and returns its fixture, so dry-run paths never construct a
client. This keeps model wiring in one place while leaving the fixture decision
visible in the node body.
"""

from __future__ import annotations

from langchain.chat_models import init_chat_model

from .settings import settings


def llm_for(node: str):
    """Return a chat model for ``node``, honoring the per-node model map.

    The model string (e.g. ``claude-opus-4-8``) infers its provider via
    langchain's ``init_chat_model``.
    """
    return init_chat_model(settings.model_for(node))
