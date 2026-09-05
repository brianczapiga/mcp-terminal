import importlib
import sys

import pytest

import terminal_mcp.backends.base as base
import terminal_mcp.backends.detect as detection
from terminal_mcp.config import Settings
from terminal_mcp.manager import TerminalManager
from terminal_mcp.models import SessionInfo


def test_import_and_create_are_side_effect_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "terminal_mcp.server", raising=False)
    monkeypatch.setattr(
        base.AppleScriptRunner, "__new__", lambda cls: pytest.fail("runner")
    )
    monkeypatch.setattr(
        detection, "detect_backend", lambda runner: pytest.fail("detect")
    )
    module = importlib.import_module("terminal_mcp.server")
    module.create_server(object())  # type: ignore[arg-type]
    import terminal_mcp_server as legacy

    assert legacy.create_server is module.create_server
    assert legacy.main is module.main
    assert legacy.TerminalManager is TerminalManager
    assert legacy.SessionInfo is SessionInfo


def test_main_builds_stdio_runtime_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    import terminal_mcp.server as module

    events = []
    config = Settings(True, frozenset(), frozenset(), False, False, 20)
    backend, manager = object(), object()

    def record(event: object, result: object = None) -> object:
        events.append(event)
        return result

    monkeypatch.setattr(module.Settings, "load", lambda: record("settings", config))
    monkeypatch.setattr(
        module.logging, "basicConfig", lambda **kw: record(("logging", kw))
    )
    monkeypatch.setattr(module, "AppleScriptRunner", lambda: record("runner", "runner"))
    monkeypatch.setattr(
        module, "detect_backend", lambda runner: record(("detect", runner), backend)
    )
    monkeypatch.setattr(
        module, "TerminalManager", lambda b, s: record(("manager", b, s), manager)
    )

    class Server:
        def run(self, transport: str) -> None:
            events.append(("run", transport))

    monkeypatch.setattr(
        module, "create_server", lambda m: record(("create", m), Server())
    )
    module.main()
    assert events[0] == "settings" and events[1][1]["stream"] is module.sys.stderr
    assert events[2:] == [
        "runner",
        ("detect", "runner"),
        ("manager", backend, config),
        ("create", manager),
        ("run", "stdio"),
    ]
