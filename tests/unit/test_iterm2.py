from __future__ import annotations

import pytest

from terminal_mcp.backends.iterm2 import ITerm2Backend
from terminal_mcp.models import SessionInfo


class RecordingRunner:
    def __init__(self, result: str = "") -> None:
        self.result = result
        self.scripts: list[str] = []

    def run(self, script: str) -> str:
        self.scripts.append(script)
        return self.result


def session() -> SessionInfo:
    return SessionInfo("w-1_s-1", "w-1", "s-1", "API", "/dev/ttys004", True, 1)


def test_lists_iterm_sessions() -> None:
    runner = RecordingRunner("w-1\ts-1\tAPI, logs\t/dev/ttys004\ttrue")
    result = ITerm2Backend(runner, clock=lambda: 9).list_sessions()
    assert result == [
        SessionInfo("w-1_s-1", "w-1", "s-1", "API, logs", "/dev/ttys004", True, 9)
    ]


def test_read_screen_preserves_whitespace_and_limits_lines() -> None:
    runner = RecordingRunner("one\n\n  three\nfour")
    assert ITerm2Backend(runner).read_screen(session(), 3) == "\n  three\nfour"
    assert "repeat with candidateSession in sessions of targetTab" in runner.scripts[0]
    assert 'unique ID of candidateSession is "s-1"' in runner.scripts[0]
    assert "if (count of matchingSessions) is not 1 then error" in runner.scripts[0]
    assert "current session" not in runner.scripts[0]


@pytest.mark.parametrize(
    ("operation", "action"),
    [
        ("send", 'write text "payload" newline: false'),
        ("key", "key code 36 using {control down}"),
        ("paste", 'write text "payload" newline: false'),
    ],
)
def test_writes_resolve_one_exact_session(operation: str, action: str) -> None:
    runner = RecordingRunner()
    backend = ITerm2Backend(runner)
    if operation == "send":
        backend.send_text(session(), "payload", False)
    elif operation == "key":
        backend.send_keypress(session(), "return", ["control"])
    else:
        backend.paste_text(session(), "payload")
    script = runner.scripts[0]
    markers = (
        "repeat with targetWindow in windows",
        "repeat with targetTab in tabs of targetWindow",
        "repeat with candidateSession in sessions of targetTab",
        'unique ID of candidateSession is "s-1"',
        "if (count of matchingSessions) is not 1 then error",
    )
    assert all(marker in script for marker in markers)
    assert action in script
    assert "current session" not in script and "front session" not in script
