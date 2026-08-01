"""Run node prompts through the local Claude Code CLI, under the host session.

Nodes call ``claude_print(node, prompt)`` to get a plain-text reply from a
``claude -p`` subprocess, reusing the host machine's already-authenticated
Claude Code session instead of a separate API client/key. Each node gets its
own named CLI session (``--name langgraph-<node>``) so concurrent nodes are
distinguishable in the host's session list, and ``CLAUDECODE`` is stripped
from the child's environment so a nested ``claude`` invocation launched from
inside a Claude Code session isn't mistaken for a sub-agent of the host
session.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from .settings import settings


class ClaudeCliError(RuntimeError):
    """Raised when the local ``claude`` CLI is missing or exits non-zero."""


def claude_print(node: str, prompt: str) -> str:
    """Run ``prompt`` through the local ``claude`` CLI and return its stdout."""
    claude_path = shutil.which("claude")
    if not claude_path:
        raise ClaudeCliError("claude CLI not found on PATH")

    name = f"langgraph-{node.replace('_', '-')}"
    model = settings.model_for(node)
    command = [claude_path, "-p", prompt, "--model", model, "--name", name]

    env = dict(os.environ)
    env.pop("CLAUDECODE", None)

    result = subprocess.run(command, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise ClaudeCliError(result.stderr.strip() or f"claude exited with {result.returncode}")
    return result.stdout.strip()
