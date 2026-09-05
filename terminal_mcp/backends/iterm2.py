# ruff: noqa: E501
"""Concrete backend for iTerm2."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from terminal_mcp.backends.base import AppleScriptRunner, applescript_string
from terminal_mcp.backends.macos_terminal import _MODIFIERS, _parse_sessions
from terminal_mcp.models import SessionInfo

_KEY_CODES = {"return": 36, "tab": 48, "escape": 53, "delete": 51}


class ITerm2Backend:
    """Operate on exact iTerm2 session identifiers."""

    name = "iTerm2"

    def __init__(
        self, runner: AppleScriptRunner, clock: Callable[[], float] = time.time
    ) -> None:
        self._runner = runner
        self._clock = clock

    def list_sessions(self) -> list[SessionInfo]:
        script = r"""
on cleanField(theValue)
    set theText to theValue as text
    set AppleScript's text item delimiters to {ASCII character 9, ASCII character 10, ASCII character 13, character id 133, character id 8232, character id 8233}
    set theParts to text items of theText
    set AppleScript's text item delimiters to " "
    set cleanText to theParts as text
    set AppleScript's text item delimiters to ""
    return cleanText
end cleanField
set fieldSeparator to ASCII character 9
set recordSeparator to ASCII character 10
set outputRecords to {}
tell application "iTerm2"
    repeat with targetWindow in windows
        set windowID to id of targetWindow as text
        repeat with targetTab in tabs of targetWindow
            repeat with targetSession in sessions of targetTab
                set sessionID to unique ID of targetSession
                set displayName to name of targetSession
                try
                    set ttyName to tty of targetSession
                on error
                    set ttyName to ""
                end try
                set end of outputRecords to my cleanField(windowID) & fieldSeparator & my cleanField(sessionID) & fieldSeparator & my cleanField(displayName) & fieldSeparator & my cleanField(ttyName) & fieldSeparator & (is processing of targetSession as text)
            end repeat
        end repeat
    end repeat
end tell
set AppleScript's text item delimiters to recordSeparator
return outputRecords as text
"""
        return _parse_sessions(self._runner.run(script), self._clock())

    @staticmethod
    def _target(session: SessionInfo) -> str:
        session_id = applescript_string(session.tab_id)
        return (
            'tell application "iTerm2"\n'
            "set matchingSessions to {}\n"
            "repeat with targetWindow in windows\n"
            "repeat with targetTab in tabs of targetWindow\n"
            "repeat with candidateSession in sessions of targetTab\n"
            f"if unique ID of candidateSession is {session_id} then set end of matchingSessions to candidateSession\n"
            "end repeat\n"
            "end repeat\n"
            "end repeat\n"
            'if (count of matchingSessions) is not 1 then error "iTerm2 session unavailable or ambiguous" number -2701\n'
            "set targetSession to item 1 of matchingSessions\n"
        )

    def read_screen(self, session: SessionInfo, lines: int) -> str:
        if lines <= 0:
            return ""
        output = self._runner.run(
            self._target(session) + "return contents of targetSession\nend tell"
        )
        return "\n".join(output.split("\n")[-lines:])

    def send_text(self, session: SessionInfo, text: str, execute: bool) -> None:
        self._runner.run(
            self._target(session)
            + f"tell targetSession to write text {applescript_string(text)} newline: {str(execute).lower()}\nend tell"
        )

    def send_keypress(
        self, session: SessionInfo, key: str, modifiers: Sequence[str]
    ) -> None:
        if set(modifiers) - _MODIFIERS:
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
        script = self._target(session) + "select targetSession\nend tell\n"
        script += 'tell application "iTerm2" to activate\n'
        script += f'tell application "System Events" to {action}'
        self._runner.run(script)

    def paste_text(self, session: SessionInfo, text: str) -> None:
        self.send_text(session, text, execute=False)
