from __future__ import annotations

import pytest

from terminal_mcp.backends.base import applescript_string
from terminal_mcp.backends.macos_terminal import MacOSTerminalBackend
from terminal_mcp.errors import MalformedResponse, UnknownSession
from terminal_mcp.models import SessionInfo


class RecordingRunner:
    def __init__(self, result: str = "") -> None:
        self.result = result
        self.scripts: list[str] = []

    def run(self, script: str) -> str:
        self.scripts.append(script)
        return self.result


def session() -> SessionInfo:
    return SessionInfo("75081_1", "75081", "1", "Build", "/dev/ttys001", False, 1)


def test_lists_terminal_sessions_from_tab_separated_records() -> None:
    runner = RecordingRunner("75081\t1\tBuild, deploy\t/dev/ttys001\tfalse")
    backend = MacOSTerminalBackend(runner, clock=lambda: 42.5)

    assert backend.list_sessions() == [
        SessionInfo(
            "75081_1", "75081", "1", "Build, deploy", "/dev/ttys001", False, 42.5
        )
    ]


@pytest.mark.parametrize(
    "output",
    [
        "75081\t1\tBuild\t/dev/ttys001",
        "75081\t1\tBuild\t/dev/ttys001\tfalse\textra",
        "75081\t1\tBuild\t\tmaybe",
        "75081\t1\tBuild\tunsafe\t/dev/ttys001\tfalse",
    ],
)
def test_malformed_session_records_raise(output: str) -> None:
    with pytest.raises(MalformedResponse):
        MacOSTerminalBackend(RecordingRunner(output)).list_sessions()


def test_read_screen_resolves_exact_window_and_tty_and_limits_lines() -> None:
    runner = RecordingRunner("heading\n  indented\n\nlast")
    result = MacOSTerminalBackend(runner).read_screen(session(), 3)

    assert result == "  indented\n\nlast"
    assert "window whose id is 75081" in runner.scripts[0]
    assert 'tty of candidateTab is "/dev/ttys001"' in runner.scripts[0]
    assert "if (count of matchingTabs) is not 1 then error" in runner.scripts[0]
    assert "tab 1 of targetWindow" not in runner.scripts[0]
    assert "front window" not in runner.scripts[0]


@pytest.mark.parametrize(
    "execute, expected", [(True, "do script"), (False, "keystroke")]
)
def test_send_text_targets_exact_tab_and_honors_execute(
    execute: bool, expected: str
) -> None:
    runner = RecordingRunner()
    text = 'echo "a\\b"' if not execute else 'echo "a\\b"\nnext'
    MacOSTerminalBackend(runner).send_text(session(), text, execute)

    script = runner.scripts[0]
    assert expected in script
    assert "window whose id is 75081" in script
    assert "tab 1 of targetWindow" not in script
    assert applescript_string(text) in script


def test_operations_reject_sessions_without_tty_without_running_script() -> None:
    runner = RecordingRunner()
    missing_tty = SessionInfo("75081_1", "75081", "1", "Build", None, False, 1)
    with pytest.raises(UnknownSession):
        MacOSTerminalBackend(runner).read_screen(missing_tty, 1)
    assert runner.scripts == []


def test_terminal_resolver_prevents_action_on_closed_or_duplicate_tty() -> None:
    runner = RecordingRunner()
    MacOSTerminalBackend(runner).send_text(session(), "pwd", True)
    script = runner.scripts[0]
    assert "if (count of matchingTabs) is not 1 then error" in script
    assert script.index(
        "if (count of matchingTabs) is not 1 then error"
    ) < script.index("do script")


@pytest.mark.parametrize(
    "text", ["one\ntwo", "one\rtwo", "bad\u0000text", "bad\u007ftext"]
)
def test_nonexecuting_terminal_text_rejects_unsafe_control_content(text: str) -> None:
    runner = RecordingRunner()
    with pytest.raises(ValueError):
        MacOSTerminalBackend(runner).send_text(session(), text, False)
    with pytest.raises(ValueError):
        MacOSTerminalBackend(runner).paste_text(session(), text)
    assert runner.scripts == []


def test_send_keypress_validates_modifiers_and_targets_exact_tab() -> None:
    runner = RecordingRunner()
    MacOSTerminalBackend(runner).send_keypress(session(), "k", ["command", "shift"])
    script = runner.scripts[0]
    assert 'keystroke "k" using {command down, shift down}' in script
    assert "selected of targetTab to true" in script
    assert "set index of targetWindow to 1" in script
    assert 'tell application "Terminal" to activate' in script
    assert 'frontmost of process "Terminal"' in script
    assert 'tty of selected tab of targetWindow is not "/dev/ttys001"' in script
    with pytest.raises(ValueError):
        MacOSTerminalBackend(runner).send_keypress(session(), "k", ["hyper"])
    with pytest.raises(ValueError):
        MacOSTerminalBackend(runner).send_keypress(session(), "\n", [])


def test_paste_uses_direct_write_without_clipboard() -> None:
    runner = RecordingRunner()
    MacOSTerminalBackend(runner).paste_text(session(), "secret text")
    script = runner.scripts[0]
    assert "selected of targetTab to true" in script
    assert "keystroke" in script
    assert "clipboard" not in script.casefold()
    assert applescript_string("secret text") in script
