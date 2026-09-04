from __future__ import annotations

import pytest

from terminal_mcp.backends.base import applescript_string
from terminal_mcp.backends.macos_terminal import MacOSTerminalBackend
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
    return SessionInfo("75081_1", "75081", "1", "Build", "/dev/ttys001", False, 1)


def test_lists_terminal_sessions_from_tab_separated_records() -> None:
    runner = RecordingRunner("75081\t1\tBuild, deploy\t/dev/ttys001\tfalse")
    backend = MacOSTerminalBackend(runner, clock=lambda: 42.5)

    assert backend.list_sessions() == [
        SessionInfo(
            "75081_1", "75081", "1", "Build, deploy", "/dev/ttys001", False, 42.5
        )
    ]
    assert "ASCII character 9" in runner.scripts[0]
    assert "ASCII character 10" in runner.scripts[0]
    assert "cleanField" in runner.scripts[0]


@pytest.mark.parametrize("output", ["", "  \n\t "])
def test_empty_session_output_returns_empty_list(output: str) -> None:
    assert MacOSTerminalBackend(RecordingRunner(output)).list_sessions() == []


def test_missing_tty_maps_to_none() -> None:
    runner = RecordingRunner("75081\t1\tBuild\t\ttrue")
    assert MacOSTerminalBackend(runner).list_sessions()[0].tty_device is None


@pytest.mark.parametrize(
    "output",
    ["75081\t1\tBuild\t/dev/ttys001", "75081\t1\tBuild\t/dev/ttys001\tfalse\textra"],
)
def test_malformed_session_rows_raise(output: str) -> None:
    with pytest.raises(MalformedResponse):
        MacOSTerminalBackend(RecordingRunner(output)).list_sessions()


def test_malformed_busy_value_raises() -> None:
    with pytest.raises(MalformedResponse):
        MacOSTerminalBackend(
            RecordingRunner("75081\t1\tBuild\t\tmaybe")
        ).list_sessions()


def test_embedded_delimiter_is_rejected_by_parser() -> None:
    with pytest.raises(MalformedResponse):
        MacOSTerminalBackend(
            RecordingRunner("75081\t1\tBuild\tunsafe\t/dev/ttys001\tfalse")
        ).list_sessions()


def test_read_screen_targets_exact_window_and_tab_and_limits_lines() -> None:
    runner = RecordingRunner("heading\n  indented\n\nlast")
    result = MacOSTerminalBackend(runner).read_screen(session(), 3)

    assert result == "  indented\n\nlast"
    assert "window whose id is 75081" in runner.scripts[0]
    assert "tab 1 of targetWindow" in runner.scripts[0]
    assert "front window" not in runner.scripts[0]


def test_applescript_string_escapes_sensitive_characters() -> None:
    literal = applescript_string('say "hi" \\ next\r\nline')
    assert literal == '"say \\"hi\\" \\\\ next\\r\\nline"'


@pytest.mark.parametrize(
    "execute, expected", [(True, "do script"), (False, "keystroke")]
)
def test_send_text_targets_exact_tab_and_honors_execute(
    execute: bool, expected: str
) -> None:
    runner = RecordingRunner()
    MacOSTerminalBackend(runner).send_text(session(), 'echo "a\\b"\nnext', execute)

    script = runner.scripts[0]
    assert expected in script
    assert "window whose id is 75081" in script and "tab 1 of targetWindow" in script
    assert applescript_string('echo "a\\b"\nnext') in script


def test_send_keypress_validates_modifiers_and_targets_exact_tab() -> None:
    runner = RecordingRunner()
    MacOSTerminalBackend(runner).send_keypress(session(), "k", ["command", "shift"])
    script = runner.scripts[0]
    assert 'keystroke "k" using {command down, shift down}' in script
    assert "selected of targetTab to true" in script
    assert "set index of targetWindow to 1" in script
    assert 'tell application "Terminal" to activate' in script
    with pytest.raises(ValueError):
        MacOSTerminalBackend(runner).send_keypress(session(), "k", ["hyper"])


def test_paste_uses_direct_write_without_clipboard() -> None:
    runner = RecordingRunner()
    MacOSTerminalBackend(runner).paste_text(session(), "secret\ntext")
    script = runner.scripts[0]
    assert "selected of targetTab to true" in script
    assert "keystroke" in script
    assert "clipboard" not in script.casefold()
    assert applescript_string("secret\ntext") in script
