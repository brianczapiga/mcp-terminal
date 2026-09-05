from __future__ import annotations

import subprocess
from typing import Any

import pytest

from terminal_mcp.manager import detect_controlling_tty


def result(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["ps"], returncode, stdout, "")


def test_current_tty_and_normalization() -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def run(*args: object, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        return result("ttys003   1\n")

    assert detect_controlling_tty(42, run) == "/dev/ttys003"
    assert calls == [
        (
            (["ps", "-o", "tty=", "-o", "ppid=", "-p", "42"],),
            {"capture_output": True, "text": True, "timeout": 1.0, "check": False},
        )
    ]


def test_parent_traversal_past_no_tty() -> None:
    outputs = iter([result("??  20\n"), result("/dev/ttys7  1\n")])
    assert detect_controlling_tty(30, lambda *a, **k: next(outputs)) == "/dev/ttys7"


@pytest.mark.parametrize("output", ["", "garbage", "tty not-a-pid", "tty 2 extra"])
def test_malformed_or_gui_output_returns_none(output: str) -> None:
    assert detect_controlling_tty(4, lambda *a, **k: result(output)) is None


def test_cycle_and_max_depth_return_none() -> None:
    assert detect_controlling_tty(4, lambda *a, **k: result("?? 4")) is None
    calls = 0

    def chain(*a: object, **k: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return result(f"?? {100 + calls}")

    assert detect_controlling_tty(100, chain) is None
    assert calls == 32


@pytest.mark.parametrize(
    "failure",
    [
        subprocess.TimeoutExpired("ps", 1),
        TimeoutError(),
        FileNotFoundError(),
        OSError(),
    ],
)
def test_subprocess_failures_return_none(failure: BaseException) -> None:
    def fail(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise failure

    assert detect_controlling_tty(9, fail) is None


def test_nonzero_returns_none() -> None:
    assert detect_controlling_tty(9, lambda *a, **k: result("ttys1 1", 2)) is None


def test_parent_traversal_obeys_overall_deadline() -> None:
    now = [10.0]
    timeouts: list[float] = []

    def run(*args: object, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        timeouts.append(float(kwargs["timeout"]))
        now[0] += 0.75
        return result(f"?? {100 + len(timeouts)}")

    assert detect_controlling_tty(100, run, clock=lambda: now[0]) is None
    assert timeouts == [1.0, 1.0, 0.5]
