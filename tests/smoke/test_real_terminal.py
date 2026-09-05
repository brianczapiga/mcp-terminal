"""Opt-in, read-only checks against an already open Terminal.app tab."""

from __future__ import annotations

import os
import sys

import pytest

from terminal_mcp.backends.base import AppleScriptRunner
from terminal_mcp.backends.macos_terminal import MacOSTerminalBackend

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        sys.platform != "darwin" or os.getenv("MCP_TERMINAL_SMOKE") != "1",
        reason="requires macOS and MCP_TERMINAL_SMOKE=1",
    ),
]


def test_screen_returns_terminal_text_instead_of_a_tab_reference() -> None:
    runner = AppleScriptRunner()
    running = runner.run('return application "Terminal" is running')
    if running != "true":
        pytest.skip("Terminal.app must already be running")
    backend = MacOSTerminalBackend(runner)
    sessions = backend.list_sessions()
    if not sessions:
        pytest.skip("Terminal.app needs an existing tab")
    session = sessions[0]
    # A direct application-object lookup avoids the resolver's list references.
    direct_script = (
        'tell application "Terminal" to return contents of '
        f"tab {int(session.tab_id)} of window id {int(session.window_id)}"
    )
    before = runner.run(direct_script)
    actual = backend.read_screen(session, 500)
    after = runner.run(direct_script)
    if before != after:
        pytest.skip("Terminal output changed during the read-only comparison")
    expected = "\n".join(before.split("\n")[-500:])
    # Do not expose the user's terminal contents in pytest failure output.
    matches = actual == expected
    assert matches, "Backend screen read differs from Terminal's screen text"
