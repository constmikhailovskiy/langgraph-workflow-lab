"""Runtime configuration shared by every workflow.

Tunables live here so experimenting with models or DRY_RUN never means editing a
graph. Values are read from the environment (loaded from .env by langgraph dev).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

#: Default model for generated LLM nodes. Overridable globally via MODEL_REASONING
#: or per-node via MODEL_<NODENAME>.
DEFAULT_MODEL = "claude-opus-4-8"


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    #: When true, no LLM calls run: nodes return deterministic fixtures so the
    #: topology can be walked in Studio without an API key. This is what makes the
    #: lab shareable and free to test. Set DRY_RUN=false for real runs.
    dry_run: bool = field(default_factory=lambda: _flag("DRY_RUN", True))

    #: Repair iterations before a failure is escalated (used by core.repair).
    repair_budget: int = field(default_factory=lambda: int(os.getenv("REPAIR_BUDGET", "4")))

    #: Global default model.
    default_model: str = field(default_factory=lambda: os.getenv("MODEL_REASONING", DEFAULT_MODEL))

    def model_for(self, node: str) -> str:
        """Model for a node: MODEL_<NODE> env override, else the global default."""
        override = os.getenv(f"MODEL_{node.upper()}")
        return override or self.default_model


settings = Settings()
