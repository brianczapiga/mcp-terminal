from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from fastmcp import Client

from terminal_mcp.config import Settings
from terminal_mcp.manager import TerminalManager
from terminal_mcp.models import SessionInfo

EXPECTED_TOOLS = {
    "list_sessions",
    "set_active_session",
    "get_screen",
    "get_all_terminal_info",
    "send_input",
    "send_keypress",
    "paste_text",
    "scroll_back",
}


class Backend:
    name = "fake"

    def __init__(self) -> None:
        self.scan_count = 0
        self.calls: list[tuple[Any, ...]] = []
        self.sessions = [
            SessionInfo("older", "w1", "t1", "Shell", "/dev/ttys1", False, 2),
            SessionInfo("newer", "w2", "t2", "Build", "/dev/ttys2", True, 9),
            SessionInfo("hidden", "w3", "t3", "Private", "/dev/ttys3", False, 10),
        ]

    def list_sessions(self) -> list[SessionInfo]:
        self.scan_count += 1
        return self.sessions

    def read_screen(self, target: SessionInfo, lines: int) -> str:
        self.calls.append(("read", target.session_id, lines))
        return f"output:{target.session_id}:{lines}"

    def send_text(self, target: SessionInfo, text: str, execute: bool) -> None:
        self.calls.append(("send", target.session_id, text, execute))

    def send_keypress(
        self, target: SessionInfo, key: str, modifiers: Sequence[str]
    ) -> None:
        self.calls.append(("key", target.session_id, key, list(modifiers)))

    def paste_text(self, target: SessionInfo, text: str) -> None:
        self.calls.append(("paste", target.session_id, text))


def settings(*, readonly: bool = True) -> Settings:
    return Settings(
        readonly=readonly,
        excluded_ttys=frozenset(),
        excluded_sessions=frozenset({"hidden"}),
        detect_self_session=False,
        allow_self_target=False,
        log_level=20,
    )


def make_server(*, readonly: bool = True) -> tuple[Any, Backend, TerminalManager]:
    from terminal_mcp.server import create_server

    backend = Backend()
    manager = TerminalManager(backend, settings(readonly=readonly))
    return create_server(manager), backend, manager


@pytest.mark.asyncio
async def test_tool_discovery_has_exact_conventional_schemas() -> None:
    server, _, _ = make_server()
    async with Client(server) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    assert set(tools) == EXPECTED_TOOLS
    assert all(
        "request" not in tool.inputSchema.get("properties", {})
        for tool in tools.values()
    )
    lines = tools["get_screen"].inputSchema["properties"]["lines"]
    assert lines["minimum"] == 1 and lines["maximum"] == 500 and lines["default"] == 100
    mode = tools["get_screen"].inputSchema["properties"]["mode"]
    assert mode["enum"] == ["focus", "recent-output", "manual"]
    assert mode["default"] == "focus"
    pages = tools["scroll_back"].inputSchema["properties"]["pages"]
    assert pages["minimum"] == 1 and pages["maximum"] == 20 and pages["default"] == 1


@pytest.mark.asyncio
async def test_read_tools_return_stable_structured_content_and_selection_modes() -> (
    None
):
    server, backend, manager = make_server()
    async with Client(server) as client:
        listed = await client.call_tool("list_sessions")
        recent = await client.call_tool(
            "get_screen", {"lines": 12, "mode": "recent-output"}
        )
        await client.call_tool("set_active_session", {"session_id": "older"})
        focus = await client.call_tool("get_screen", {"mode": "focus"})
        manual = await client.call_tool("get_screen", {"mode": "manual"})

    assert listed.structured_content == {
        "sessions": [
            {
                "session_id": "older",
                "name": "Shell",
                "tty": "/dev/ttys1",
                "busy": False,
                "active": False,
            },
            {
                "session_id": "newer",
                "name": "Build",
                "tty": "/dev/ttys2",
                "busy": True,
                "active": False,
            },
        ],
        "total": 2,
        "active_session_id": None,
    }
    assert recent.structured_content == {
        "session_id": "newer",
        "mode": "recent-output",
        "content": "output:newer:12",
        "lines": 12,
    }
    assert focus.structured_content["session_id"] == "older"
    assert focus.structured_content["mode"] == "focus"
    assert manual.structured_content["session_id"] == "older"
    assert manager.active_session_id == "older"
    assert ("read", "newer", 12) in backend.calls


@pytest.mark.asyncio
async def test_manual_without_active_and_unknown_or_excluded_are_tool_errors() -> None:
    server, _, _ = make_server()
    async with Client(server) as client:
        manual = await client.call_tool(
            "get_screen", {"mode": "manual"}, raise_on_error=False
        )
        missing = await client.call_tool(
            "set_active_session", {"session_id": "missing"}, raise_on_error=False
        )
        hidden = await client.call_tool(
            "set_active_session", {"session_id": "hidden"}, raise_on_error=False
        )
    assert manual.is_error and missing.is_error and hidden.is_error


@pytest.mark.asyncio
async def test_all_info_scans_once_and_never_exposes_excluded_sessions() -> None:
    server, backend, _ = make_server()
    async with Client(server) as client:
        result = await client.call_tool("get_all_terminal_info", {"lines": 8})
    data = result.structured_content
    assert backend.scan_count == 1
    assert data is not None
    assert data["session_ids"] == ["older", "newer"]
    assert data["default_session_id"] == "newer"
    assert data["total"] == 2
    assert [item["session_id"] for item in data["sessions"]] == ["older", "newer"]
    assert "hidden" not in repr(data)


@pytest.mark.asyncio
async def test_write_tools_policy_and_explicit_or_default_target() -> None:
    readonly_server, _, _ = make_server(readonly=True)
    async with Client(readonly_server) as client:
        blocked = await client.call_tool(
            "send_input", {"text": "sensitive"}, raise_on_error=False
        )
    assert blocked.is_error

    server, backend, _ = make_server(readonly=False)
    async with Client(server) as client:
        sent = await client.call_tool("send_input", {"text": "hi", "execute": False})
        key = await client.call_tool(
            "send_keypress",
            {"key": "k", "modifiers": ["command"], "session_id": "older"},
        )
        pasted = await client.call_tool("paste_text", {"text": "hello"})
    assert sent.structured_content == {
        "success": True,
        "session_id": "newer",
        "executed": False,
    }
    assert key.structured_content == {"success": True, "session_id": "older"}
    assert pasted.structured_content == {"success": True, "session_id": "newer"}
    assert backend.calls == [
        ("send", "newer", "hi", False),
        ("key", "older", "k", ["command"]),
        ("paste", "newer", "hello"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("get_screen", {"lines": 0}),
        ("get_screen", {"lines": 501}),
        ("get_screen", {"mode": "guess"}),
        ("get_all_terminal_info", {"lines": 0}),
        ("scroll_back", {"pages": 0}),
        ("scroll_back", {"pages": 21}),
    ],
)
async def test_invalid_inputs_are_rejected_at_schema_boundary(
    tool: str, arguments: dict[str, Any]
) -> None:
    server, _, _ = make_server()
    async with Client(server) as client:
        result = await client.call_tool(tool, arguments, raise_on_error=False)
    assert result.is_error


@pytest.mark.asyncio
async def test_resource_template_and_substantive_prompts() -> None:
    server, _, _ = make_server()
    async with Client(server) as client:
        templates = await client.list_resource_templates()
        resource = await client.read_resource("terminal://session/older")
        prompts = {prompt.name for prompt in await client.list_prompts()}
        guide = await client.get_prompt("terminal_workflow_guide")
        summary = await client.get_prompt(
            "terminal_session_summary", {"session_id": "older"}
        )
    assert [str(item.uriTemplate) for item in templates] == [
        "terminal://session/{session_id}"
    ]
    assert resource[0].mimeType == "text/plain"
    assert resource[0].text == "output:older:100"
    assert prompts == {
        "terminal_workflow_guide",
        "terminal_session_summary",
        "terminal_command_suggestion",
        "terminal_troubleshooting",
    }
    assert "read" in guide.messages[0].content.text.casefold()
    assert "older" in summary.messages[0].content.text


def test_import_and_create_server_have_no_backend_or_applescript_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    import terminal_mcp.server as module

    monkeypatch.setattr(
        module, "detect_backend", lambda runner: pytest.fail("backend detected")
    )
    monkeypatch.setattr(
        module, "AppleScriptRunner", lambda: pytest.fail("runner created")
    )
    reloaded = importlib.reload(module)
    manager = TerminalManager(Backend(), settings())
    reloaded.create_server(manager)


def test_main_builds_runtime_dependencies_and_runs_stdio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import terminal_mcp.server as module

    events: list[Any] = []
    fake_settings = settings()
    fake_backend = Backend()
    fake_manager = object()

    monkeypatch.setattr(module.Settings, "load", lambda: fake_settings)
    monkeypatch.setattr(
        module, "AppleScriptRunner", lambda: events.append("runner") or "runner"
    )
    monkeypatch.setattr(
        module,
        "detect_backend",
        lambda runner: events.append(("detect", runner)) or fake_backend,
    )
    monkeypatch.setattr(
        module,
        "TerminalManager",
        lambda backend, config: (
            events.append(("manager", backend, config)) or fake_manager
        ),
    )

    class Server:
        def run(self, transport: str) -> None:
            events.append(("run", transport))

    monkeypatch.setattr(
        module,
        "create_server",
        lambda manager: events.append(("create", manager)) or Server(),
    )
    module.main()
    assert events[-1] == ("run", "stdio")


def test_compatibility_module_reexports_public_contract() -> None:
    import terminal_mcp_server as legacy
    from terminal_mcp.server import create_server, main

    assert legacy.TerminalManager is TerminalManager
    assert legacy.SessionInfo is SessionInfo
    assert legacy.create_server is create_server
    assert legacy.main is main
