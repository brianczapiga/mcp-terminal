"""Shared domain models for terminal MCP backends."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionInfo:
    """A point-in-time description of a terminal session."""

    session_id: str
    window_id: str
    tab_id: str
    name: str
    tty_device: str | None
    is_busy: bool
    observed_at: float
