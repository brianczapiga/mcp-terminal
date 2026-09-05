from __future__ import annotations

import pytest

from terminal_mcp.backends.base import applescript_string
from terminal_mcp.backends.iterm2 import ITerm2Backend
from terminal_mcp.errors import MalformedResponse
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
    assert "cleanField" in runner.scripts[0]


@pytest.mark.parametrize("output", ["", " \n "])
def test_empty_output(output: str) -> None:
    assert ITerm2Backend(RecordingRunner(output)).list_sessions() == []


def test_missing_tty() -> None:
    assert (
        ITerm2Backend(RecordingRunner("w-1\ts-1\tAPI\t\tfalse"))
        .list_sessions()[0]
        .tty_device
        is None
    )


@pytest.mark.parametrize(
    "output",
    [
        "w-1\ts-1\tAPI\t/dev/ttys004",
        "w-1\ts-1\tAPI\t/dev/ttys004\twat",
        "w-1\ts-1\tAPI\tx\t/dev/ttys004\ttrue",
    ],
)
def test_malformed_responses(output: str) -> None:
    with pytest.raises(MalformedResponse):
        ITerm2Backend(RecordingRunner(output)).list_sessions()


def test_read_screen_preserves_whitespace_and_limits_lines() -> None:
    runner = RecordingRunner("one\n\n  three\nfour")
    assert ITerm2Backend(runner).read_screen(session(), 3) == "\n  three\nfour"
    assert "repeat with targetWindow in windows" in runner.scripts[0]
    assert "repeat with targetTab in tabs of targetWindow" in runner.scripts[0]
    assert "repeat with candidateSession in sessions of targetTab" in runner.scripts[0]
    assert 'unique ID of candidateSession is "s-1"' in runner.scripts[0]
    assert "if (count of matchingSessions) is not 1 then error" in runner.scripts[0]
    assert "number -2701" in runner.scripts[0]
    assert "current session" not in runner.scripts[0]


@pytest.mark.parametrize("execute", [True, False])
def test_send_text_targets_exact_session(execute: bool) -> None:
    runner = RecordingRunner()
    ITerm2Backend(runner).send_text(session(), 'echo "x\\y"\nnext', execute)
    script = runner.scripts[0]
    assert 'unique ID of candidateSession is "s-1"' in script
    assert applescript_string('echo "x\\y"\nnext') in script
    assert f"newline: {str(execute).lower()}" in script


def test_keypress_and_modifiers_target_exact_session() -> None:
    runner = RecordingRunner()
    ITerm2Backend(runner).send_keypress(session(), "return", ["control", "option"])
    script = runner.scripts[0]
    assert 'unique ID of candidateSession is "s-1"' in script
    assert "key code 36 using {control down, option down}" in script
    assert 'tell application "iTerm2" to activate' in script
    with pytest.raises(ValueError):
        ITerm2Backend(runner).send_keypress(session(), "not-a-key", [])


def test_paste_writes_directly_without_clipboard() -> None:
    runner = RecordingRunner()
    ITerm2Backend(runner).paste_text(session(), "secret\ntext")
    script = runner.scripts[0]
    assert 'write text "secret\\ntext" newline: false' in script
    assert "repeat with candidateSession in sessions of targetTab" in script
    assert "if (count of matchingSessions) is not 1 then error" in script
    assert "clipboard" not in script.casefold()


def test_nonpositive_read_does_not_run_script() -> None:
    runner = RecordingRunner("ignored")
    assert ITerm2Backend(runner).read_screen(session(), 0) == ""
    assert ITerm2Backend(runner).read_screen(session(), -1) == ""
    assert runner.scripts == []
