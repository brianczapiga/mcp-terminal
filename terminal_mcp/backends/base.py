"""Backend protocol and shared AppleScript execution support."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from terminal_mcp.errors import (
    ApplicationUnavailable,
    AutomationDenied,
    ScriptFailed,
    ScriptTimedOut,
)
from terminal_mcp.models import SessionInfo


@runtime_checkable
class TerminalBackend(Protocol):
    """Operations implemented by a supported terminal application."""

    name: str

    def list_sessions(self) -> list[SessionInfo]: ...

    def read_screen(self, session: SessionInfo, lines: int) -> str: ...

    def send_text(self, session: SessionInfo, text: str, execute: bool) -> None: ...

    def send_keypress(
        self, session: SessionInfo, key: str, modifiers: Sequence[str]
    ) -> None: ...

    def paste_text(self, session: SessionInfo, text: str) -> None: ...


class AppleScriptRunner:
    """Run AppleScript with bounded execution and sanitized domain errors."""

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    def run(self, script: str) -> str:
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (subprocess.TimeoutExpired, TimeoutError):
            raise ScriptTimedOut("AppleScript execution timed out") from None
        except FileNotFoundError:
            raise ApplicationUnavailable("osascript is unavailable") from None

        if result.returncode != 0:
            if self._is_automation_denial(result.stderr):
                raise AutomationDenied(
                    "Automation permission was denied; allow terminal automation "
                    "in macOS System Settings"
                )
            raise ScriptFailed("AppleScript execution failed")

        return result.stdout.strip()

    @staticmethod
    def _is_automation_denial(stderr: str) -> bool:
        normalized = stderr.casefold()
        indicators = (
            "not authorized",
            "not permitted",
            "permission denied",
            "-1743",
        )
        return any(indicator in normalized for indicator in indicators)
