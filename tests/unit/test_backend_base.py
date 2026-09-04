from __future__ import annotations

import logging
import subprocess
from collections.abc import Sequence
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from terminal_mcp.backends.base import AppleScriptRunner, TerminalBackend
from terminal_mcp.errors import (
    ApplicationUnavailable,
    AutomationDenied,
    ScriptFailed,
    ScriptTimedOut,
)
from terminal_mcp.models import SessionInfo


def completed_process(
    *, returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["osascript"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_session_info_is_immutable() -> None:
    session = SessionInfo("1", "2", "3", "shell", None, False, 123.0)

    with pytest.raises(FrozenInstanceError):
        setattr(session, "name", "changed")  # noqa: B010


def test_terminal_backend_is_runtime_checkable() -> None:
    class Backend:
        name = "test"

        def list_sessions(self) -> list[SessionInfo]:
            return []

        def read_screen(self, session: SessionInfo, lines: int) -> str:
            return ""

        def send_text(self, session: SessionInfo, text: str, execute: bool) -> None:
            return None

        def send_keypress(
            self, session: SessionInfo, key: str, modifiers: Sequence[str]
        ) -> None:
            return None

        def paste_text(self, session: SessionInfo, text: str) -> None:
            return None

    backend: TerminalBackend = Backend()
    assert isinstance(backend, TerminalBackend)


def test_run_removes_only_process_framing_newline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return completed_process(stdout="\n  indented text  \n\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert AppleScriptRunner().run("return text") == "\n  indented text  \n"


def test_run_passes_configured_timeout_and_text_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        observed["args"] = args
        observed["kwargs"] = kwargs
        return completed_process()

    monkeypatch.setattr(subprocess, "run", fake_run)

    AppleScriptRunner(timeout_seconds=2.5).run("return 1")

    assert observed == {
        "args": (["osascript", "-"],),
        "kwargs": {
            "input": "return 1",
            "capture_output": True,
            "text": True,
            "timeout": 2.5,
            "check": False,
        },
    }


@pytest.mark.parametrize(
    "stderr",
    [
        "Not authorized to send Apple events to Terminal.",
        "Automation permission denied",
    ],
)
def test_run_classifies_automation_denial(
    monkeypatch: pytest.MonkeyPatch, stderr: str
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: completed_process(returncode=1, stderr=stderr),
    )

    with pytest.raises(AutomationDenied, match="Automation permission"):
        AppleScriptRunner().run("tell application Terminal")


def test_run_classifies_generic_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: completed_process(
            returncode=1, stderr="unexpected AppleScript failure"
        ),
    )

    with pytest.raises(ScriptFailed, match="AppleScript execution failed"):
        AppleScriptRunner().run("broken script")


def test_run_does_not_classify_unrelated_permission_denial_as_automation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: completed_process(
            returncode=1, stderr="filesystem permission denied"
        ),
    )

    with pytest.raises(ScriptFailed):
        AppleScriptRunner().run("broken script")


def test_run_maps_subprocess_timeout_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    def time_out(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="osascript", timeout=1)

    monkeypatch.setattr(subprocess, "run", time_out)

    with pytest.raises(ScriptTimedOut, match="timed out"):
        AppleScriptRunner().run("slow script")


def test_run_maps_builtin_timeout_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def time_out(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise TimeoutError("slow secret details")

    monkeypatch.setattr(subprocess, "run", time_out)

    with pytest.raises(ScriptTimedOut, match="timed out"):
        AppleScriptRunner().run("slow script")


def test_run_does_not_chain_errors_that_may_contain_script_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "TOP-SECRET-SCRIPT-CONTENT"

    def time_out(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            cmd=["osascript", "-e", f'return "{secret}"'], timeout=1
        )

    monkeypatch.setattr(subprocess, "run", time_out)

    with pytest.raises(ScriptTimedOut) as error:
        AppleScriptRunner().run(f'return "{secret}"')

    assert error.value.__cause__ is None


def test_run_maps_missing_osascript(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("sensitive executable path")

    monkeypatch.setattr(subprocess, "run", unavailable)

    with pytest.raises(ApplicationUnavailable, match="osascript is unavailable"):
        AppleScriptRunner().run("return 1")


def test_run_maps_launch_os_error_without_exposing_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "TOP-SECRET-EXECUTABLE-PATH"

    def unavailable(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise PermissionError(secret)

    monkeypatch.setattr(subprocess, "run", unavailable)

    with pytest.raises(ApplicationUnavailable) as error:
        AppleScriptRunner().run("return 1")

    assert secret not in str(error.value)


def test_run_does_not_expose_terminal_secrets(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "TOP-SECRET-TERMINAL-CONTENT"
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: completed_process(
            returncode=1, stdout=secret, stderr=f"failure: {secret}"
        ),
    )

    with caplog.at_level(logging.DEBUG), pytest.raises(ScriptFailed) as error:
        AppleScriptRunner().run(f'return "{secret}"')

    assert secret not in str(error.value)
    assert secret not in caplog.text


def test_run_keeps_terminal_secret_out_of_process_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "TOP-SECRET-TERMINAL-INPUT"
    observed_argv: list[str] = []

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        observed_argv.extend(argv)
        return completed_process()

    monkeypatch.setattr(subprocess, "run", fake_run)

    AppleScriptRunner().run(f'return "{secret}"')

    assert all(secret not in argument for argument in observed_argv)
