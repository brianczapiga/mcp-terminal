# ruff: noqa: E501
"""Concrete backend for Apple's Terminal application."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from terminal_mcp.backends.base import AppleScriptRunner, applescript_string
from terminal_mcp.errors import MalformedResponse
from terminal_mcp.models import SessionInfo

_MODIFIERS = {"command", "control", "option", "shift"}
_KEY_CODES = {"return": 36, "tab": 48, "escape": 53, "delete": 51}


def _parse_sessions(output: str, observed_at: float) -> list[SessionInfo]:
    if not output.strip():
        return []
    sessions: list[SessionInfo] = []
    for row in output.splitlines():
        if not row.strip():
            continue
        fields = row.split("\t")
        if len(fields) != 5:
            raise MalformedResponse("Terminal returned a malformed session record")
        window_id, tab_id, name, tty, busy_text = fields
        if not window_id or not tab_id:
            raise MalformedResponse("Terminal returned an incomplete session record")
        if busy_text == "true":
            busy = True
        elif busy_text == "false":
            busy = False
        else:
            raise MalformedResponse("Terminal returned an invalid busy value")
        sessions.append(
            SessionInfo(
                f"{window_id}_{tab_id}",
                window_id,
                tab_id,
                name,
                tty or None,
                busy,
                observed_at,
            )
        )
    return sessions


class MacOSTerminalBackend:
    """Operate on exact Terminal.app window/tab pairs."""

    name = "Terminal"

    def __init__(
        self, runner: AppleScriptRunner, clock: Callable[[], float] = time.time
    ) -> None:
        self._runner = runner
        self._clock = clock

    def list_sessions(self) -> list[SessionInfo]:
        script = r"""
on cleanField(theValue)
    set theText to theValue as text
    set AppleScript's text item delimiters to {ASCII character 9, ASCII character 10, ASCII character 13}
    set theParts to text items of theText
    set AppleScript's text item delimiters to " "
    set cleanText to theParts as text
    set AppleScript's text item delimiters to ""
    return cleanText
end cleanField
set fieldSeparator to ASCII character 9
set recordSeparator to ASCII character 10
set outputRecords to {}
tell application "Terminal"
    repeat with targetWindow in windows
        set windowID to id of targetWindow as text
        repeat with tabIndex from 1 to count tabs of targetWindow
            set targetTab to tab tabIndex of targetWindow
            set displayName to custom title of targetTab
            if displayName is "" then set displayName to name of targetTab
            try
                set ttyName to tty of targetTab
            on error
                set ttyName to ""
            end try
            set end of outputRecords to my cleanField(windowID) & fieldSeparator & tabIndex & fieldSeparator & my cleanField(displayName) & fieldSeparator & my cleanField(ttyName) & fieldSeparator & (busy of targetTab as text)
        end repeat
    end repeat
end tell
set AppleScript's text item delimiters to recordSeparator
return outputRecords as text
"""
        return _parse_sessions(self._runner.run(script), self._clock())

    @staticmethod
    def _target(session: SessionInfo) -> str:
        try:
            window_id = str(int(session.window_id))
            tab_id = str(int(session.tab_id))
        except ValueError:
            raise ValueError("Terminal window and tab IDs must be integers") from None
        return (
            'tell application "Terminal"\n'
            f"set targetWindow to first window whose id is {window_id}\n"
            f"set targetTab to tab {tab_id} of targetWindow\n"
        )

    def read_screen(self, session: SessionInfo, lines: int) -> str:
        if lines < 0:
            raise ValueError("lines must not be negative")
        output = self._runner.run(
            self._target(session) + "return contents of targetTab\nend tell"
        )
        if lines == 0:
            return ""
        return "\n".join(output.split("\n")[-lines:])

    def send_text(self, session: SessionInfo, text: str, execute: bool) -> None:
        if execute:
            self._runner.run(
                self._target(session)
                + f"do script {applescript_string(text)} in targetTab\nend tell"
            )
        else:
            self._runner.run(
                self._focus_script(session)
                + "\n"
                + 'tell application "System Events" to keystroke '
                + applescript_string(text)
            )

    def _focus_script(self, session: SessionInfo) -> str:
        return (
            self._target(session)
            + "set selected of targetTab to true\n"
            + "set index of targetWindow to 1\n"
            + "end tell\n"
            + 'tell application "Terminal" to activate'
        )

    def send_keypress(
        self, session: SessionInfo, key: str, modifiers: Sequence[str]
    ) -> None:
        invalid = set(modifiers) - _MODIFIERS
        if invalid:
            raise ValueError("unsupported key modifier")
        using = ""
        if modifiers:
            using = " using {" + ", ".join(f"{item} down" for item in modifiers) + "}"
        if key in _KEY_CODES:
            action = f"key code {_KEY_CODES[key]}{using}"
        elif len(key) == 1:
            action = f"keystroke {applescript_string(key)}{using}"
        else:
            raise ValueError("key must be one character or a supported named key")
        script = self._focus_script(session) + "\n"
        script += f'tell application "System Events" to {action}'
        self._runner.run(script)

    def paste_text(self, session: SessionInfo, text: str) -> None:
        self.send_text(session, text, execute=False)
