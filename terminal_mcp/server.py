"""FastMCP server contract and runtime entry point."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from typing import Annotated, Literal, TypeVar

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from terminal_mcp.backends.base import AppleScriptRunner
from terminal_mcp.backends.detect import detect_backend
from terminal_mcp.backends.lazy import LazyTerminalBackend
from terminal_mcp.config import Settings
from terminal_mcp.errors import (
    AccessibilityDenied,
    ApplicationUnavailable,
    AutomationDenied,
    ExcludedSession,
    MalformedResponse,
    ScriptFailed,
    ScriptTimedOut,
    TerminalMcpError,
    UnknownSession,
    WriteDisabled,
)
from terminal_mcp.manager import TerminalManager
from terminal_mcp.models import (
    AggregateResult,
    ListSessionsResult,
    ScreenResult,
    ScrollResult,
    SessionInfo,
    SessionView,
    SetActiveResult,
    WriteResult,
)

T = TypeVar("T")
LineCount = Annotated[int, Field(ge=1, le=500)]
PageCount = Annotated[int, Field(ge=1, le=20)]
ScreenMode = Literal["focus", "automatic", "manual"]
MAX_AGGREGATE_SESSIONS = 20
MAX_AGGREGATE_CHARACTERS = 200_000
logger = logging.getLogger(__name__)
ERROR_MESSAGES = {
    ApplicationUnavailable: (
        "No supported terminal application is accessible. Open Terminal.app or "
        "iTerm2 and retry the tool call. If neither can be detected, check that "
        "the server is running on macOS with osascript available. Failed detection "
        "is retried on the next call; restarting the MCP server is not required."
    ),
    AccessibilityDenied: (
        "macOS blocked terminal keyboard input because Accessibility permission "
        "is missing. Ask the user to open System Settings > Privacy & Security > "
        "Accessibility and enable the app launching this MCP server (the MCP "
        "client, such as Codex or Claude Desktop, or its terminal host). Use the "
        "app identified by macOS; the server cannot determine that app reliably. "
        "After granting access, fully quit and restart that app, then retry the "
        "requested operation. Restarting alone does not grant permission."
    ),
    AutomationDenied: (
        "macOS denied Automation permission. Ask the user to open System Settings "
        "> Privacy & Security > Automation and allow the app launching this MCP "
        "server (the MCP client or its terminal host) to control Terminal/iTerm2 "
        "and System Events as requested by macOS. After granting access, restart "
        "that app and retry. Keyboard input may separately require Accessibility."
    ),
    ExcludedSession: "The requested terminal session is excluded by policy.",
    MalformedResponse: "The terminal returned an unreadable response.",
    ScriptFailed: "The terminal automation operation failed.",
    ScriptTimedOut: "The terminal automation operation timed out.",
    UnknownSession: "The requested terminal session is unavailable.",
    WriteDisabled: (
        "Terminal writes are disabled by policy. If the user wants to enable "
        "writes, set MCP_TERMINAL_READONLY=0 in the .env selected by "
        "MCP_TERMINAL_ENV_FILE (or the server working directory's .env if unset). "
        "Process environment values override .env, so check the MCP client's "
        "server environment too. Then restart the MCP server/client and retry."
    ),
}


def _session_data(
    session: SessionInfo,
    active_session_id: str | None,
    content: str | None = None,
    content_truncated: bool = False,
) -> SessionView:
    return SessionView(
        session_id=session.session_id,
        name=session.name,
        tty=session.tty_device,
        busy=session.is_busy,
        active=session.session_id == active_session_id,
        content=content,
        content_truncated=content_truncated,
    )


def _tool_errors(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except TerminalMcpError as error:
        logger.warning("Terminal operation failed: %s", type(error).__name__)
        message = ERROR_MESSAGES.get(type(error), "The terminal operation failed.")
        raise ToolError(message) from None
    except ToolError:
        raise
    except Exception as error:
        logger.error("Unexpected terminal operation failure: %s", type(error).__name__)
        raise ToolError("The terminal operation failed unexpectedly.") from None


def create_server(manager: TerminalManager) -> FastMCP:
    """Create an in-memory server around an already configured manager."""
    server = FastMCP(
        "Terminal MCP",
        instructions=(
            "Inspect terminal sessions safely and perform explicit writes. "
            "When a tool reports a permission or read-only policy error, explain "
            "its recovery steps to the user and wait for the required change "
            "before retrying. macOS Automation and Accessibility are separate "
            "permissions; do not assume a successful read permits keyboard input. "
            "Do not treat generic failures or timeouts as proof of missing "
            "permissions. After a write times out, inspect the terminal before "
            "retrying because the write may have occurred."
        ),
        strict_input_validation=True,
    )

    @server.tool(description="List eligible terminal sessions without changing them.")
    def list_sessions() -> ListSessionsResult:
        def operation() -> ListSessionsResult:
            sessions = manager.list_sessions()
            return ListSessionsResult(
                sessions=[
                    _session_data(session, manager.active_session_id)
                    for session in sessions
                ],
                total=len(sessions),
                active_session_id=manager.active_session_id,
            )

        return _tool_errors(operation)

    @server.tool(
        description="Select an eligible session for subsequent focused operations."
    )
    def set_active_session(session_id: str) -> SetActiveResult:
        def operation() -> SetActiveResult:
            manager.set_active_session(session_id)
            return SetActiveResult(success=True, session_id=session_id)

        return _tool_errors(operation)

    @server.tool(
        description=(
            "Read terminal screen content without side effects. Focus and automatic "
            "use the active session or a stable fallback; manual requires an active "
            "session."
        )
    )
    def get_screen(lines: LineCount = 100, mode: ScreenMode = "focus") -> ScreenResult:
        def operation() -> ScreenResult:
            if mode == "automatic":
                target_id, content = manager.read_automatic_screen(lines)
            elif mode == "manual":
                if manager.active_session_id is None:
                    raise ToolError("Manual mode requires an active terminal session")
                target_id, content = manager.read_screen(None, lines)
            else:
                target_id, content = manager.read_screen(None, lines)
            return ScreenResult(
                session_id=target_id, mode=mode, content=content, lines=lines
            )

        return _tool_errors(operation)

    @server.tool(
        description="Read a coherent snapshot of every eligible terminal session."
    )
    def get_all_terminal_info(lines: LineCount = 100) -> AggregateResult:
        def operation() -> AggregateResult:
            snapshot = manager.capture_snapshot(
                lines, MAX_AGGREGATE_SESSIONS, MAX_AGGREGATE_CHARACTERS
            )
            sessions = [item.session for item in snapshot.sessions]
            default_id = snapshot.default_session_id
            details = [
                _session_data(
                    item.session,
                    snapshot.active_session_id,
                    item.content,
                    item.content_truncated,
                )
                for item in snapshot.sessions
            ]
            return AggregateResult(
                session_ids=[session.session_id for session in sessions],
                sessions=details,
                default_session_id=default_id,
                total=snapshot.total,
                lines=lines,
                truncated=snapshot.truncated,
                omitted_session_ids=list(snapshot.omitted_session_ids),
            )

        return _tool_errors(operation)

    @server.tool(
        description=(
            "Type text into a terminal and optionally execute it; writes terminal "
            "state. Provide session_id or first select an active session."
        )
    )
    def send_input(
        text: str, execute: bool = True, session_id: str | None = None
    ) -> WriteResult:
        def operation() -> WriteResult:
            target_id = manager.send_input(session_id, text, execute)
            return WriteResult(success=True, session_id=target_id, executed=execute)

        return _tool_errors(operation)

    @server.tool(
        description=(
            "Send a keypress to a terminal; writes terminal state. "
            "Provide session_id or first select an active session. "
            "Use one character or return, tab, escape, delete, up, down, left, right. "
            "Optional modifiers: command, control, option, shift."
        )
    )
    def send_keypress(
        key: str,
        modifiers: list[str] | None = None,
        session_id: str | None = None,
    ) -> WriteResult:
        def operation() -> WriteResult:
            target_id = manager.send_keypress(session_id, key, modifiers or ())
            return WriteResult(success=True, session_id=target_id, executed=None)

        return _tool_errors(operation)

    @server.tool(
        description=(
            "Paste literal text into a terminal; writes terminal state. "
            "Provide session_id or first select an active session."
        )
    )
    def paste_text(text: str, session_id: str | None = None) -> WriteResult:
        def operation() -> WriteResult:
            target_id = manager.paste_text(session_id, text)
            return WriteResult(success=True, session_id=target_id, executed=None)

        return _tool_errors(operation)

    @server.tool(
        description="Read buffered prior screen captures without changing the terminal."
    )
    def scroll_back(
        pages: PageCount = 1, session_id: str | None = None
    ) -> ScrollResult:
        def operation() -> ScrollResult:
            target_id, content = manager.scroll_back_target(session_id, pages)
            return ScrollResult(
                session_id=target_id,
                pages=pages,
                content=content,
            )

        return _tool_errors(operation)

    @server.resource(
        "terminal://session/{session_id}",
        description="Current content for one exact eligible terminal session.",
        mime_type="text/plain",
    )
    def terminal_session(session_id: str) -> str:
        return _tool_errors(lambda: manager.get_session_content(session_id, 100))

    @server.prompt(
        description="Safe workflow for inspecting and interacting with terminals."
    )
    def terminal_workflow_guide() -> str:
        return (
            "First list sessions, then read the selected screen. Prefer read-only "
            "inspection; "
            "before any write, confirm the target session and explain the side effect."
        )

    @server.prompt(description="Template for summarizing a named terminal session.")
    def terminal_session_summary(session_id: str) -> str:
        return (
            f"Read terminal session {session_id}, then summarize its current task, "
            "recent "
            "output, failures, and likely next safe step. Do not send input."
        )

    @server.prompt(description="Template for proposing, but not executing, a command.")
    def terminal_command_suggestion(goal: str) -> str:
        return (
            f"Suggest a terminal command for this goal: {goal}. Explain risks and "
            "assumptions; "
            "do not execute or paste the command."
        )

    @server.prompt(
        description="Template for diagnosing terminal output without hidden writes."
    )
    def terminal_troubleshooting(issue: str) -> str:
        return (
            f"Troubleshoot this terminal issue: {issue}. Inspect available output, "
            "identify "
            "evidence and propose reversible checks. Do not write to a terminal."
        )

    return server


def main() -> None:
    """Configure runtime dependencies and serve MCP over standard I/O."""
    settings = Settings.load()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
    runner = AppleScriptRunner()
    backend = LazyTerminalBackend(lambda: detect_backend(runner))
    manager = TerminalManager(backend, settings)
    create_server(manager).run("stdio")


__all__ = ["create_server", "main"]
