from __future__ import annotations

import threading
from collections.abc import Sequence

import pytest

from terminal_mcp.config import Settings
from terminal_mcp.errors import ExcludedSession, UnknownSession, WriteDisabled
from terminal_mcp.manager import TerminalManager
from terminal_mcp.models import SessionInfo


def session(sid: str, *, tty: str | None = None, observed: float = 0) -> SessionInfo:
    return SessionInfo(sid, "w", "t", sid, tty, False, observed)


class Backend:
    name = "fake"

    def __init__(self, scans: list[list[SessionInfo]]) -> None:
        self.scans = scans
        self.scan_count = 0
        self.calls: list[tuple[object, ...]] = []

    def list_sessions(self) -> list[SessionInfo]:
        result = self.scans[min(self.scan_count, len(self.scans) - 1)]
        self.scan_count += 1
        return result

    def read_screen(self, target: SessionInfo, lines: int) -> str:
        self.calls.append(("read", target.session_id, lines))
        return f"{target.session_id}:{lines}:{len(self.calls)}"

    def send_text(self, target: SessionInfo, text: str, execute: bool) -> None:
        self.calls.append(("send", target.session_id, text, execute))

    def send_keypress(
        self, target: SessionInfo, key: str, modifiers: Sequence[str]
    ) -> None:
        self.calls.append(("key", target.session_id, key, modifiers))

    def paste_text(self, target: SessionInfo, text: str) -> None:
        self.calls.append(("paste", target.session_id, text))


def settings(**changes: object) -> Settings:
    values = dict(
        readonly=True,
        excluded_ttys=frozenset(),
        excluded_sessions=frozenset(),
        detect_self_session=False,
        allow_self_target=False,
        log_level=20,
    )
    values.update(changes)
    return Settings(**values)  # type: ignore[arg-type]


def test_scan_cache_force_replacement_and_stale_cleanup() -> None:
    now = [10.0]
    backend = Backend([[session("a")], [session("b")]])
    manager = TerminalManager(backend, settings(), clock=lambda: now[0])
    assert [s.session_id for s in manager.list_sessions()] == ["a"]
    manager.get_session_content("a", 5)
    manager.set_active_session("a")
    now[0] = 11.9
    assert [s.session_id for s in manager.list_sessions()] == ["a"]
    assert backend.scan_count == 1
    assert [s.session_id for s in manager.list_sessions(force=True)] == ["b"]
    assert manager.active_session_id is None
    assert "a" not in manager.output_buffers


def test_concurrent_forced_scan_cannot_publish_out_of_order() -> None:
    first_started = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()

    class BlockingBackend(Backend):
        def list_sessions(self) -> list[SessionInfo]:
            scan_number = self.scan_count
            self.scan_count += 1
            if scan_number == 0:
                first_started.set()
                assert release_first.wait(timeout=2)
                return [session("a")]
            second_started.set()
            return [session("b")]

    backend = BlockingBackend([[]])
    manager = TerminalManager(backend, settings())
    first = threading.Thread(target=manager.list_sessions)
    second = threading.Thread(target=lambda: manager.list_sessions(force=True))
    first.start()
    assert first_started.wait(timeout=2)
    second.start()
    second_entered_while_first_blocked = second_started.wait(timeout=0.05)
    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive() and not second.is_alive()
    assert not second_entered_while_first_blocked
    assert second_started.is_set()
    assert list(manager.sessions) == ["b"]


def test_concurrent_initial_scans_do_not_resurrect_stale_sessions() -> None:
    first_started = threading.Event()
    release_first = threading.Event()

    class BlockingBackend(Backend):
        def list_sessions(self) -> list[SessionInfo]:
            self.scan_count += 1
            first_started.set()
            assert release_first.wait(timeout=2)
            return [session("only")]

    backend = BlockingBackend([[]])
    manager = TerminalManager(backend, settings())
    threads = [threading.Thread(target=manager.list_sessions) for _ in range(2)]
    threads[0].start()
    assert first_started.wait(timeout=2)
    threads[1].start()
    release_first.set()
    for thread in threads:
        thread.join(timeout=2)

    assert backend.scan_count == 1
    assert list(manager.sessions) == ["only"]


def test_exclusions_and_explicit_override_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "terminal_mcp.manager.detect_controlling_tty", lambda: "/dev/ttys9"
    )
    backend = Backend(
        [
            [
                session("id", tty="/dev/ttys1"),
                session("self", tty="/dev/ttys9"),
                session("ok", observed=3),
            ]
        ]
    )
    manager = TerminalManager(
        backend,
        settings(
            excluded_sessions=frozenset({"id"}),
            excluded_ttys=frozenset({"/dev/ttys1"}),
            detect_self_session=True,
            allow_self_target=True,
        ),
    )
    assert [s.session_id for s in manager.list_sessions()] == ["ok"]
    assert manager.most_recent_session().session_id == "ok"
    with pytest.raises(ExcludedSession):
        manager.set_active_session("self")
    assert manager.get_session_content("self", 2) == "self:2:1"


def test_self_detection_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "terminal_mcp.manager.detect_controlling_tty", lambda: "/dev/ttys9"
    )
    manager = TerminalManager(
        Backend([[session("self", tty="/dev/ttys9")]]), settings()
    )
    assert [s.session_id for s in manager.list_sessions()] == ["self"]


def test_active_validation_fallback_and_recent_ties() -> None:
    backend = Backend([[session("z", observed=5), session("a", observed=5)]])
    manager = TerminalManager(backend, settings())
    assert manager.most_recent_session().session_id == "a"
    assert manager.get_active_session_content(7) == "a:7:1"
    manager.set_active_session("z")
    assert manager.get_active_session_content(4) == "z:4:2"
    with pytest.raises(UnknownSession):
        manager.set_active_session("missing")


@pytest.mark.parametrize("lines", [0, -3])
def test_nonpositive_read_returns_empty_without_backend_or_buffer(lines: int) -> None:
    backend = Backend([[session("a")]])
    manager = TerminalManager(backend, settings())

    assert manager.get_session_content("a", lines) == ""
    assert backend.calls == []
    assert "a" not in manager.output_buffers


def test_read_excluded_without_override_fails() -> None:
    manager = TerminalManager(
        Backend([[session("x")]]),
        settings(excluded_sessions=frozenset({"x"})),
    )
    with pytest.raises(ExcludedSession):
        manager.get_session_content("x", 4)


def test_every_write_is_gated_and_writable_delegates_exact_arguments() -> None:
    backend = Backend([[session("a")]])
    blocked = TerminalManager(backend, settings())
    for operation in (
        lambda: blocked.send_input("a", "hi", True),
        lambda: blocked.send_keypress("a", "K", ("command",)),
        lambda: blocked.paste_text("a", "secret"),
    ):
        with pytest.raises(WriteDisabled):
            operation()
    assert backend.calls == []

    writable = TerminalManager(backend, settings(readonly=False))
    writable.send_input("a", "hi", True)
    writable.send_keypress("a", "K", ("command",))
    writable.paste_text("a", "secret")
    assert backend.calls == [
        ("send", "a", "hi", True),
        ("key", "a", "K", ("command",)),
        ("paste", "a", "secret"),
    ]


def test_buffers_are_bounded_and_scroll_back_is_deterministic() -> None:
    backend = Backend([[session("a")]])
    manager = TerminalManager(backend, settings(), buffer_size=3)
    for _ in range(5):
        manager.get_session_content("a", 5)
    assert list(manager.output_buffers["a"]) == ["a:5:3", "a:5:4", "a:5:5"]
    assert manager.scroll_back("a", pages=1) == "a:5:3\na:5:4\na:5:5"
    assert manager.scroll_back("a", pages=0) == ""
