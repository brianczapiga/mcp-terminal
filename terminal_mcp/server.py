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
from terminal_mcp.config import Settings
from terminal_mcp.errors import (
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
ScreenMode = Literal["focus", "recent-output", "manual"]
MAX_AGGREGATE_SESSIONS = 20
MAX_AGGREGATE_CHARACTERS = 200_000
logger = logging.getLogger(__name__)
ERROR_MESSAGES = {
    ApplicationUnavailable: "No supported terminal application is available.",
    AutomationDenied: "Terminal automation permission is required.",
    ExcludedSession: "The requested terminal session is excluded by policy.",
    MalformedResponse: "The terminal returned an unreadable response.",
    ScriptFailed: "The terminal automation operation failed.",
    ScriptTimedOut: "The terminal automation operation timed out.",
    UnknownSession: "The requested terminal session is unavailable.",
    WriteDisabled: "Terminal writes are disabled by policy.",
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
    except Exception as error:
        logger.error("Unexpected terminal operation failure: %s", type(error).__name__)
        raise ToolError("The terminal operation failed unexpectedly.") from None


def _target_id(manager: TerminalManager, session_id: str | None) -> str:
    if session_id is not None:
        return session_id
    if manager.active_session_id is not None:
        return manager.active_session_id
    return manager.most_recent_session().session_id


def create_server(manager: TerminalManager) -> FastMCP:
    """Create an in-memory server around an already configured manager."""
    server = FastMCP(
        "Terminal MCP",
        instructions="Inspect terminal sessions safely and perform explicit writes.",
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
        description="Read terminal screen content; this has no terminal side effects."
    )
    def get_screen(lines: LineCount = 100, mode: ScreenMode = "focus") -> ScreenResult:
        def operation() -> ScreenResult:
            if mode == "recent-output":
                target_id = manager.most_recent_session().session_id
            elif mode == "manual":
                if manager.active_session_id is None:
                    raise ToolError("Manual mode requires an active terminal session")
                target_id = manager.active_session_id
            else:
                target_id = _target_id(manager, None)
            content = manager.get_session_content(target_id, lines)
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
            default_id = manager.active_session_id or snapshot.default_session_id
            details = [
                _session_data(
                    item.session,
                    manager.active_session_id,
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
            "state."
        )
    )
    def send_input(
        text: str, execute: bool = True, session_id: str | None = None
    ) -> WriteResult:
        def operation() -> WriteResult:
            target_id = _target_id(manager, session_id)
            manager.send_input(target_id, text, execute)
            return WriteResult(success=True, session_id=target_id, executed=execute)

        return _tool_errors(operation)

    @server.tool(description="Send a keypress to a terminal; writes terminal state.")
    def send_keypress(
        key: str,
        modifiers: list[str] | None = None,
        session_id: str | None = None,
    ) -> WriteResult:
        def operation() -> WriteResult:
            target_id = _target_id(manager, session_id)
            manager.send_keypress(target_id, key, modifiers or ())
            return WriteResult(success=True, session_id=target_id, executed=None)

        return _tool_errors(operation)

    @server.tool(
        description="Paste literal text into a terminal; writes terminal state."
    )
    def paste_text(text: str, session_id: str | None = None) -> WriteResult:
        def operation() -> WriteResult:
            target_id = _target_id(manager, session_id)
            manager.paste_text(target_id, text)
            return WriteResult(success=True, session_id=target_id, executed=None)

        return _tool_errors(operation)

    @server.tool(
        description="Read buffered prior screen captures without changing the terminal."
    )
    def scroll_back(
        pages: PageCount = 1, session_id: str | None = None
    ) -> ScrollResult:
        def operation() -> ScrollResult:
            target_id = _target_id(manager, session_id)
            return ScrollResult(
                session_id=target_id,
                pages=pages,
                content=manager.scroll_back(target_id, pages),
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
    backend = detect_backend(runner)
    manager = TerminalManager(backend, settings)
    create_server(manager).run("stdio")


__all__ = ["create_server", "main"]
