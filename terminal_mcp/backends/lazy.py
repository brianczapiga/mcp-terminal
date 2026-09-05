"""Defer application discovery until a terminal operation needs it."""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence

from terminal_mcp.backends.base import TerminalBackend
from terminal_mcp.models import SessionInfo


class LazyTerminalBackend:
    """Cache successful discovery; let failed discovery retry on the next call.

    Operations are never retried internally, especially writes whose outcome may
    be uncertain. Once selected, the backend stays fixed to preserve session identity.
    """

    def __init__(self, factory: Callable[[], TerminalBackend]) -> None:
        self._factory = factory
        self._backend: TerminalBackend | None = None
        self._lock = threading.Lock()

    def _get_backend(self) -> TerminalBackend:
        with self._lock:
            if self._backend is None:
                self._backend = self._factory()
            return self._backend

    @property
    def name(self) -> str:
        return self._get_backend().name

    def list_sessions(self) -> list[SessionInfo]:
        return self._get_backend().list_sessions()

    def read_screen(self, session: SessionInfo, lines: int) -> str:
        return self._get_backend().read_screen(session, lines)

    def send_text(self, session: SessionInfo, text: str, execute: bool) -> None:
        self._get_backend().send_text(session, text, execute)

    def send_keypress(
        self, session: SessionInfo, key: str, modifiers: Sequence[str]
    ) -> None:
        self._get_backend().send_keypress(session, key, modifiers)

    def paste_text(self, session: SessionInfo, text: str) -> None:
        self._get_backend().paste_text(session, text)
