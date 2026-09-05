from __future__ import annotations

import logging
import subprocess
from typing import Any

import pytest

from terminal_mcp.backends.base import AppleScriptRunner
from terminal_mcp.errors import (
    AccessibilityDenied,
    ApplicationUnavailable,
    AutomationDenied,
    ScriptFailed,
    ScriptTimedOut,
    UnknownSession,
)


def completed_process(
    *, returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["osascript"], returncode=returncode, stdout=stdout, stderr=stderr
    )


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
    ("stderr", "error"),
    [
        ("Not authorized to send Apple events to Terminal.", AutomationDenied),
        ("Automation permission denied", AutomationDenied),
        ("osascript is not allowed to send keystrokes. (1002)", AccessibilityDenied),
        ("osascript is not allowed assistive access. (-1719)", AccessibilityDenied),
        ("Not allowed to access assistive devices", AccessibilityDenied),
        ("unrelated operation failed (1002)", ScriptFailed),
        ("invalid index (-1719)", ScriptFailed),
        ("execution error: unavailable (-2701)", UnknownSession),
        ("unexpected AppleScript failure", ScriptFailed),
        ("filesystem permission denied", ScriptFailed),
    ],
)
def test_run_classifies_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch, stderr: str, error: type[Exception]
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: completed_process(returncode=1, stderr=stderr),
    )

    with pytest.raises(error):
        AppleScriptRunner().run("tell application Terminal")


@pytest.mark.parametrize(
    "failure", [subprocess.TimeoutExpired(cmd="osascript", timeout=1), TimeoutError()]
)
def test_run_maps_timeouts(
    monkeypatch: pytest.MonkeyPatch, failure: BaseException
) -> None:
    def time_out(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise failure

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


@pytest.mark.parametrize(
    "failure", [FileNotFoundError("SECRET"), PermissionError("SECRET")]
)
def test_run_redacts_launch_errors(
    monkeypatch: pytest.MonkeyPatch, failure: OSError
) -> None:
    def unavailable(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise failure

    monkeypatch.setattr(subprocess, "run", unavailable)

    with pytest.raises(ApplicationUnavailable) as error:
        AppleScriptRunner().run("return 1")

    assert "SECRET" not in str(error.value)


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
