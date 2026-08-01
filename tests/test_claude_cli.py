from __future__ import annotations

import os
import subprocess
from unittest.mock import patch

import pytest

from lab.core.claude_cli import ClaudeCliError, claude_print


def test_claude_print_uses_host_cli_session_and_returns_stdout() -> None:
    inherited_path = os.environ.get("PATH", "")

    with (
        patch("lab.core.claude_cli.shutil.which", return_value="/usr/local/bin/claude"),
        patch("lab.core.claude_cli.settings.model_for", return_value="opus"),
        patch("lab.core.claude_cli.subprocess.run") as run,
        patch.dict(os.environ, {"CLAUDECODE": "1", "PATH": inherited_path}),
    ):
        run.return_value = subprocess.CompletedProcess([], 0, "  answer\n", "")

        result = claude_print("story_planner", "Plan this")

    assert result == "answer"
    command = run.call_args.args[0]
    assert command[:3] == ["/usr/local/bin/claude", "-p", "Plan this"]
    assert "--model" in command
    assert command[command.index("--model") + 1] == "opus"
    assert command[command.index("--name") + 1] == "langgraph-story-planner"
    assert run.call_args.kwargs["env"].get("CLAUDECODE") is None


def test_claude_print_reports_cli_failure() -> None:
    with (
        patch("lab.core.claude_cli.shutil.which", return_value="claude"),
        patch("lab.core.claude_cli.settings.model_for", return_value="opus"),
        patch("lab.core.claude_cli.subprocess.run") as run,
    ):
        run.return_value = subprocess.CompletedProcess([], 2, "", "not authenticated")

        with pytest.raises(ClaudeCliError, match="not authenticated"):
            claude_print("story_planner", "Plan this")

