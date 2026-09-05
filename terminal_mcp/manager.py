"""Session selection, caching, and safety policy for terminal backends."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence

from terminal_mcp.backends.base import TerminalBackend
from terminal_mcp.config import Settings
from terminal_mcp.errors import ExcludedSession, UnknownSession, WriteDisabled
from terminal_mcp.models import SessionInfo

SCAN_INTERVAL_SECONDS = 2.0
SELF_TTY_TIMEOUT_SECONDS = 1.0
MAX_PARENT_DEPTH = 32
SCROLL_ENTRIES_PER_PAGE = 5


def _normalize_tty(tty: str) -> str:
    return tty if tty.startswith("/dev/") else f"/dev/{tty}"


def detect_controlling_tty(
    pid: int | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    *,
    clock: Callable[[], float] = time.monotonic,
    overall_timeout: float = 2.0,
) -> str | None:
    """Best-effort discovery of this process tree's controlling TTY."""
    current_pid = os.getpid() if pid is None else pid
    visited: set[int] = set()
    deadline = clock() + max(0.0, overall_timeout)

    for _ in range(MAX_PARENT_DEPTH):
        if current_pid <= 1 or current_pid in visited:
            return None
        remaining = deadline - clock()
        if remaining <= 0:
            return None
        visited.add(current_pid)
        try:
            result = runner(
                ["ps", "-o", "tty=", "-o", "ppid=", "-p", str(current_pid)],
                capture_output=True,
                text=True,
                timeout=min(SELF_TTY_TIMEOUT_SECONDS, remaining),
                check=False,
            )
        except (subprocess.TimeoutExpired, TimeoutError, FileNotFoundError, OSError):
            return None
        if result.returncode != 0:
            return None

        fields = result.stdout.strip().split()
        if len(fields) != 2:
            return None
        tty, parent_text = fields
        try:
            parent_pid = int(parent_text)
        except ValueError:
            return None
        if tty not in {"??", "?", "-", ""}:
            return _normalize_tty(tty)
        current_pid = parent_pid
    return None


class TerminalManager:
    """Manage discovered sessions while enforcing selection and write policy."""

    def __init__(
        self,
        backend: TerminalBackend,
        settings: Settings,
        clock: Callable[[], float] = time.monotonic,
        *,
        buffer_size: int = 500,
    ) -> None:
        self.backend = backend
        self.settings = settings
        self.clock = clock
        self.active_session_id: str | None = None
        self.sessions: dict[str, SessionInfo] = {}
        self.output_buffers: dict[str, deque[str]] = {}
        self._last_scan_at: float | None = None
        self._buffer_size = max(1, buffer_size)
        self._lock = threading.RLock()
        self._excluded_ttys = set(settings.excluded_ttys)
        if settings.detect_self_session:
            detected_tty = detect_controlling_tty()
            if detected_tty is not None:
                self._excluded_ttys.add(detected_tty)

    def _is_excluded(self, session: SessionInfo) -> bool:
        return session.session_id in self.settings.excluded_sessions or (
            session.tty_device is not None
            and _normalize_tty(session.tty_device) in self._excluded_ttys
        )

    def list_sessions(self, force: bool = False) -> list[SessionInfo]:
        with self._lock:
            now = self.clock()
            if (
                force
                or self._last_scan_at is None
                or now - self._last_scan_at >= SCAN_INTERVAL_SECONDS
            ):
                discovered = self.backend.list_sessions()
                self.sessions = {item.session_id: item for item in discovered}
                self._last_scan_at = now
                stale_ids = self.output_buffers.keys() - self.sessions.keys()
                for session_id in stale_ids:
                    del self.output_buffers[session_id]
                if self.active_session_id is not None:
                    active = self.sessions.get(self.active_session_id)
                    if active is None or self._is_excluded(active):
                        self.active_session_id = None
            return [
                item for item in self.sessions.values() if not self._is_excluded(item)
            ]

    def most_recent_session(self) -> SessionInfo:
        with self._lock:
            sessions = self.list_sessions()
            if not sessions:
                raise UnknownSession("No eligible terminal sessions are available")
            return min(sessions, key=lambda item: (-item.observed_at, item.session_id))

    def set_active_session(self, session_id: str) -> None:
        with self._lock:
            self.list_sessions()
            target = self.sessions.get(session_id)
            if target is None:
                raise UnknownSession(f"Unknown terminal session: {session_id}")
            if self._is_excluded(target):
                raise ExcludedSession(f"Terminal session is excluded: {session_id}")
            self.active_session_id = session_id

    def _resolve_target(self, session_id: str | None) -> SessionInfo:
        with self._lock:
            explicitly_supplied = session_id is not None
            self.list_sessions()
            if session_id is None:
                session_id = self.active_session_id
                if session_id is None:
                    return self.most_recent_session()
            target = self.sessions.get(session_id)
            if target is None:
                raise UnknownSession(f"Unknown terminal session: {session_id}")
            if self._is_excluded(target) and not (
                explicitly_supplied and self.settings.allow_self_target
            ):
                raise ExcludedSession(f"Terminal session is excluded: {session_id}")
            return target

    def get_session_content(self, session_id: str, lines: int = 100) -> str:
        with self._lock:
            target = self._resolve_target(session_id)
            if lines <= 0:
                return ""
            return self._read_and_buffer(target, lines)

    def read_snapshot_session(self, session: SessionInfo, lines: int = 100) -> str:
        """Read a session from a prior scan without triggering another discovery."""
        with self._lock:
            known = self.sessions.get(session.session_id)
            if known != session or self._is_excluded(session):
                raise UnknownSession("The terminal session snapshot is no longer valid")
            if lines <= 0:
                return ""
            return self._read_and_buffer(session, lines)

    def _read_and_buffer(self, target: SessionInfo, lines: int) -> str:
        content = self.backend.read_screen(target, lines)
        buffer = self.output_buffers.setdefault(
            target.session_id, deque(maxlen=self._buffer_size)
        )
        buffer.append(content)
        return content

    def get_active_session_content(self, lines: int = 100) -> str:
        with self._lock:
            target = self._resolve_target(None)
            return self.get_session_content(target.session_id, lines)

    def scroll_back(self, session_id: str, pages: int = 1) -> str:
        with self._lock:
            self._resolve_target(session_id)
            if pages <= 0:
                return ""
            buffer = self.output_buffers.get(session_id)
            if not buffer:
                return ""
            count = min(pages * SCROLL_ENTRIES_PER_PAGE, len(buffer))
            return "\n".join(list(buffer)[-count:])

    def _require_write(self) -> None:
        if self.settings.readonly:
            raise WriteDisabled("Terminal writes are disabled")

    def send_input(
        self, session_id: str | None, text: str, execute: bool = True
    ) -> None:
        self._require_write()
        with self._lock:
            self.backend.send_text(self._resolve_target(session_id), text, execute)

    def send_keypress(
        self,
        session_id: str | None,
        key: str,
        modifiers: Sequence[str] = (),
    ) -> None:
        self._require_write()
        with self._lock:
            self.backend.send_keypress(self._resolve_target(session_id), key, modifiers)

    def paste_text(self, session_id: str | None, text: str) -> None:
        self._require_write()
        with self._lock:
            self.backend.paste_text(self._resolve_target(session_id), text)
