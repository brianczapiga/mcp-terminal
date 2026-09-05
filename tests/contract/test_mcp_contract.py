from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import pytest
from fastmcp import Client

from terminal_mcp.config import Settings
from terminal_mcp.errors import AutomationDenied, ScriptFailed
from terminal_mcp.manager import TerminalManager
from terminal_mcp.models import SessionInfo

TOOLS = {
    "list_sessions",
    "set_active_session",
    "get_screen",
    "get_all_terminal_info",
    "send_input",
    "send_keypress",
    "paste_text",
    "scroll_back",
}
PROMPTS = {
    "terminal_workflow_guide",
    "terminal_session_summary",
    "terminal_command_suggestion",
    "terminal_troubleshooting",
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


def settings(readonly: bool = True) -> Settings:
    return Settings(readonly, frozenset(), frozenset({"hidden"}), False, False, 20)


def setup(readonly: bool = True) -> tuple[Any, Backend, TerminalManager]:
    from terminal_mcp.server import create_server

    backend = Backend()
    manager = TerminalManager(backend, settings(readonly))
    return create_server(manager), backend, manager


@pytest.mark.asyncio
async def test_discovery_and_schema_contract() -> None:
    server, _, _ = setup()
    async with Client(server) as client:
        tools = {item.name: item for item in await client.list_tools()}
    assert set(tools) == TOOLS
    assert all(
        "request" not in tool.inputSchema.get("properties", {})
        for tool in tools.values()
    )
    lines = tools["get_screen"].inputSchema["properties"]["lines"]
    pages = tools["scroll_back"].inputSchema["properties"]["pages"]
    mode = tools["get_screen"].inputSchema["properties"]["mode"]
    assert (lines["minimum"], lines["maximum"], lines["default"]) == (1, 500, 100)
    assert (pages["minimum"], pages["maximum"], pages["default"]) == (1, 20, 1)
    assert (mode["enum"], mode["default"]) == (
        ["focus", "recent-output", "manual"],
        "focus",
    )
    outputs = {
        "list_sessions": {"sessions", "total", "active_session_id"},
        "set_active_session": {"success", "session_id"},
        "get_screen": {"session_id", "mode", "content", "lines"},
        "get_all_terminal_info": {
            "session_ids",
            "sessions",
            "default_session_id",
            "total",
            "lines",
            "truncated",
            "omitted_session_ids",
        },
        "send_input": {"success", "session_id"},
        "send_keypress": {"success", "session_id"},
        "paste_text": {"success", "session_id"},
        "scroll_back": {"session_id", "pages", "content"},
    }
    for name, properties in outputs.items():
        assert properties <= set(tools[name].outputSchema["properties"])
        assert properties <= set(tools[name].outputSchema["required"])


@pytest.mark.asyncio
async def test_reads_selection_and_structured_shapes() -> None:
    server, _, _ = setup()
    async with Client(server) as client:
        no_active = await client.call_tool(
            "get_screen", {"mode": "manual"}, raise_on_error=False
        )
        listed = await client.call_tool("list_sessions")
        recent = await client.call_tool(
            "get_screen", {"lines": 12, "mode": "recent-output"}
        )
        active = await client.call_tool("set_active_session", {"session_id": "older"})
        focus = await client.call_tool("get_screen", {"mode": "focus"})
        manual = await client.call_tool("get_screen", {"mode": "manual"})
    sessions = listed.structured_content["sessions"]
    assert "active terminal session" in no_active.content[0].text
    assert "unexpected" not in no_active.content[0].text.casefold()
    assert [item["session_id"] for item in sessions] == ["older", "newer"]
    assert {"session_id", "name", "tty", "busy", "active"} <= set(sessions[0])
    assert active.structured_content == {"success": True, "session_id": "older"}
    assert recent.structured_content == {
        "session_id": "newer",
        "mode": "recent-output",
        "content": "output:newer:12",
        "lines": 12,
    }
    assert [result.structured_content["mode"] for result in (focus, manual)] == [
        "focus",
        "manual",
    ]
    assert all(
        result.structured_content["session_id"] == "older" for result in (focus, manual)
    )


@pytest.mark.asyncio
async def test_all_info_is_one_scan_and_excludes_hidden_even_after_cache_expiry() -> (
    None
):
    server, backend, manager = setup()
    manager.set_active_session("older")
    capture = manager.capture_snapshot

    def mutate_after_capture(*args: Any) -> Any:
        snapshot = capture(*args)
        manager.active_session_id = "newer"
        return snapshot

    cast(Any, manager).capture_snapshot = mutate_after_capture
    async with Client(server) as client:
        result = await client.call_tool("get_all_terminal_info", {"lines": 8})
    data = cast(dict[str, Any], result.structured_content)
    assert backend.scan_count == 1
    assert (data["session_ids"], data["default_session_id"], data["total"]) == (
        ["newer", "older"],
        "older",
        2,
    )
    assert [item["content"] for item in data["sessions"]] == [
        "output:newer:8",
        "output:older:8",
    ]
    assert [item["session_id"] for item in data["sessions"] if item["active"]] == [
        "older"
    ]
    assert "hidden" not in repr(data)


@pytest.mark.asyncio
async def test_write_policy_errors_and_successful_delegation() -> None:
    blocked_server, _, _ = setup()
    async with Client(blocked_server) as client:
        blocked = await client.call_tool(
            "send_input", {"text": "secret"}, raise_on_error=False
        )
        unknown = await client.call_tool(
            "set_active_session", {"session_id": "missing"}, raise_on_error=False
        )
        excluded = await client.call_tool(
            "paste_text", {"text": "x", "session_id": "hidden"}, raise_on_error=False
        )
    assert all(item.is_error for item in (blocked, unknown, excluded))

    server, _, _ = setup(False)
    async with Client(server) as client:
        results = [
            await client.call_tool("send_input", {"text": "hi", "execute": False}),
            await client.call_tool(
                "send_keypress",
                {"key": "k", "modifiers": ["command"], "session_id": "older"},
            ),
            await client.call_tool("paste_text", {"text": "hello"}),
        ]
    assert [item.structured_content["session_id"] for item in results] == [
        "newer",
        "older",
        "newer",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool,args",
    [
        ("get_screen", {"lines": 0}),
        ("get_screen", {"lines": 501}),
        ("get_screen", {"mode": "guess"}),
        ("get_all_terminal_info", {"lines": 0}),
        ("scroll_back", {"pages": 0}),
        ("scroll_back", {"pages": 21}),
    ],
)
async def test_schema_rejects_invalid_input(tool: str, args: dict[str, Any]) -> None:
    server, _, _ = setup()
    async with Client(server) as client:
        assert (await client.call_tool(tool, args, raise_on_error=False)).is_error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        AutomationDenied("SECRET"),
        ScriptFailed("SECRET"),
        RuntimeError("SECRET"),
    ],
)
async def test_domain_details_do_not_reach_protocol_or_logs(
    failure: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    server, backend, _ = setup()
    backend.read_screen = lambda target, lines: (_ for _ in ()).throw(failure)  # type: ignore[method-assign]
    async with Client(server) as client:
        result = await client.call_tool("get_screen", raise_on_error=False)
    assert result.is_error and "SECRET" not in repr(result.content) + caplog.text


@pytest.mark.asyncio
async def test_resource_and_prompts_are_discoverable_and_substantive() -> None:
    server, _, _ = setup()
    async with Client(server) as client:
        templates = await client.list_resource_templates()
        resource = await client.read_resource("terminal://session/older")
        prompts = {item.name for item in await client.list_prompts()}
        calls = [
            await client.get_prompt("terminal_workflow_guide"),
            await client.get_prompt("terminal_session_summary", {"session_id": "ARG"}),
            await client.get_prompt("terminal_command_suggestion", {"goal": "ARG"}),
            await client.get_prompt("terminal_troubleshooting", {"issue": "ARG"}),
        ]
    assert [str(item.uriTemplate) for item in templates] == [
        "terminal://session/{session_id}"
    ]
    assert (resource[0].mimeType, resource[0].text) == (
        "text/plain",
        "output:older:100",
    )
    assert prompts == PROMPTS
    texts = [item.messages[0].content.text for item in calls]
    assert "read" in texts[0].casefold()
    assert all("ARG" in text and "do not" in text.casefold() for text in texts[1:])
