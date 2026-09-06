"""Exercise startup and recovery over a real stdio MCP connection."""

from __future__ import annotations

import sys
import textwrap

import pytest
from fastmcp import Client


@pytest.mark.asyncio
async def test_stdio_handshake_and_tool_recovery_with_failing_applescript() -> None:
    script = textwrap.dedent(
        """
        from terminal_mcp.backends.base import AppleScriptRunner
        from terminal_mcp.errors import ScriptTimedOut
        from terminal_mcp.server import main

        responses = iter([
            ScriptTimedOut("initial OS probe timed out"),
            "false", "true", "Terminal",
            "42\\t1\\tShell\\t/dev/ttys123\\tfalse",
            "terminal output",
        ])
        def run(self, script):
            result = next(responses)
            if isinstance(result, Exception):
                raise result
            return result
        AppleScriptRunner.run = run
        main()
        """
    )
    config = {
        "mcpServers": {
            "terminal": {
                "command": sys.executable,
                "args": ["-c", script],
                "env": {
                    "MCP_TERMINAL_READONLY": "1",
                    "MCP_TERMINAL_DETECT_SELF_SESSION": "0",
                    "MCP_TERMINAL_EXCLUDED_TTYS": "",
                    "MCP_TERMINAL_EXCLUDED_SESSIONS": "",
                },
            }
        }
    }
    async with Client(config, timeout=5) as client:
        assert len(await client.list_tools()) == 8
        failed = await client.call_tool("list_sessions", raise_on_error=False)
        assert failed.is_error
        message = " ".join(item.text for item in failed.content if item.type == "text")
        assert "timed out" in message
        recovered = await client.call_tool("list_sessions")
        assert (
            recovered.structured_content["sessions"][0]["session_id"]
            == "terminal_ttys123"
        )
        screen = await client.call_tool("get_screen")
        assert screen.structured_content["content"] == "terminal output"
