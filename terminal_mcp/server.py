"""FastMCP server contract and runtime entry point."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from typing import Annotated, Any, Literal, TypeVar

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from terminal_mcp.backends.base import AppleScriptRunner
from terminal_mcp.backends.detect import detect_backend
from terminal_mcp.config import Settings
from terminal_mcp.errors import TerminalMcpError
from terminal_mcp.manager import TerminalManager
from terminal_mcp.models import SessionInfo

T = TypeVar("T")
LineCount = Annotated[int, Field(ge=1, le=500)]
PageCount = Annotated[int, Field(ge=1, le=20)]
ScreenMode = Literal["focus", "recent-output", "manual"]


def _session_data(
    session: SessionInfo, active_session_id: str | None
) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "name": session.name,
        "tty": session.tty_device,
        "busy": session.is_busy,
        "active": session.session_id == active_session_id,
    }


def _tool_errors(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except TerminalMcpError as error:
        raise ToolError(str(error)) from None


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
    def list_sessions() -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            sessions = manager.list_sessions()
            return {
                "sessions": [
                    _session_data(session, manager.active_session_id)
                    for session in sessions
                ],
                "total": len(sessions),
                "active_session_id": manager.active_session_id,
            }

        return _tool_errors(operation)

    @server.tool(
        description="Select an eligible session for subsequent focused operations."
    )
    def set_active_session(session_id: str) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            manager.set_active_session(session_id)
            return {"success": True, "session_id": session_id}

        return _tool_errors(operation)

    @server.tool(
        description="Read terminal screen content; this has no terminal side effects."
    )
    def get_screen(
        lines: LineCount = 100, mode: ScreenMode = "focus"
    ) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            if mode == "recent-output":
                target_id = manager.most_recent_session().session_id
            elif mode == "manual":
                if manager.active_session_id is None:
                    raise ToolError("Manual mode requires an active terminal session")
                target_id = manager.active_session_id
            else:
                target_id = _target_id(manager, None)
            content = manager.get_session_content(target_id, lines)
            return {
                "session_id": target_id,
                "mode": mode,
                "content": content,
                "lines": lines,
            }

        return _tool_errors(operation)

    @server.tool(
        description="Read a coherent snapshot of every eligible terminal session."
    )
    def get_all_terminal_info(lines: LineCount = 100) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            sessions = manager.list_sessions()
            default_id = (
                manager.active_session_id
                if manager.active_session_id is not None
                else (
                    min(
                        sessions, key=lambda item: (-item.observed_at, item.session_id)
                    ).session_id
                    if sessions
                    else None
                )
            )
            details = []
            for session in sessions:
                item = _session_data(session, manager.active_session_id)
                item["content"] = manager.get_session_content(session.session_id, lines)
                details.append(item)
            return {
                "session_ids": [session.session_id for session in sessions],
                "sessions": details,
                "default_session_id": default_id,
                "total": len(sessions),
                "lines": lines,
            }

        return _tool_errors(operation)

    @server.tool(
        description=(
            "Type text into a terminal and optionally execute it; writes terminal "
            "state."
        )
    )
    def send_input(
        text: str, execute: bool = True, session_id: str | None = None
    ) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            target_id = _target_id(manager, session_id)
            manager.send_input(target_id, text, execute)
            return {"success": True, "session_id": target_id, "executed": execute}

        return _tool_errors(operation)

    @server.tool(description="Send a keypress to a terminal; writes terminal state.")
    def send_keypress(
        key: str,
        modifiers: list[str] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            target_id = _target_id(manager, session_id)
            manager.send_keypress(target_id, key, modifiers or ())
            return {"success": True, "session_id": target_id}

        return _tool_errors(operation)

    @server.tool(
        description="Paste literal text into a terminal; writes terminal state."
    )
    def paste_text(text: str, session_id: str | None = None) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            target_id = _target_id(manager, session_id)
            manager.paste_text(target_id, text)
            return {"success": True, "session_id": target_id}

        return _tool_errors(operation)

    @server.tool(
        description="Read buffered prior screen captures without changing the terminal."
    )
    def scroll_back(
        pages: PageCount = 1, session_id: str | None = None
    ) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            target_id = _target_id(manager, session_id)
            return {
                "session_id": target_id,
                "pages": pages,
                "content": manager.scroll_back(target_id, pages),
            }

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
