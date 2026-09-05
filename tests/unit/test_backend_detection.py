from __future__ import annotations

import pytest

import terminal_mcp.backends as backends
from terminal_mcp.backends.detect import detect_backend
from terminal_mcp.backends.iterm2 import ITerm2Backend
from terminal_mcp.backends.macos_terminal import MacOSTerminalBackend
from terminal_mcp.errors import ApplicationUnavailable, AutomationDenied


def test_backend_package_exports_complete_public_surface() -> None:
    assert backends.__all__ == [
        "AppleScriptRunner",
        "ITerm2Backend",
        "MacOSTerminalBackend",
        "TerminalBackend",
        "detect_backend",
    ]
    assert backends.AppleScriptRunner is not None
    assert backends.TerminalBackend is not None


class SequenceRunner:
    def __init__(self, results: list[str | Exception]) -> None:
        self.results = iter(results)
        self.scripts: list[str] = []

    def run(self, script: str) -> str:
        self.scripts.append(script)
        result = next(self.results)
        if isinstance(result, Exception):
            raise result
        return result


def test_prefers_running_accessible_iterm() -> None:
    runner = SequenceRunner(["true", "ok"])
    assert isinstance(detect_backend(runner), ITerm2Backend)
    assert all("launch" not in script.casefold() for script in runner.scripts)


def test_falls_back_to_terminal_when_iterm_not_running() -> None:
    runner = SequenceRunner(["false", "true", "ok"])
    assert isinstance(detect_backend(runner), MacOSTerminalBackend)


def test_falls_back_to_terminal_when_iterm_probe_fails() -> None:
    runner = SequenceRunner(["true", ApplicationUnavailable("gone"), "true", "ok"])
    assert isinstance(detect_backend(runner), MacOSTerminalBackend)


def test_raises_when_neither_application_is_running() -> None:
    with pytest.raises(ApplicationUnavailable):
        detect_backend(SequenceRunner(["false", "false"]))


def test_does_not_swallow_permission_denial_for_running_app() -> None:
    runner = SequenceRunner(["true", AutomationDenied("denied")])
    with pytest.raises(AutomationDenied):
        detect_backend(runner)
