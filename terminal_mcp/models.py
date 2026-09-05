"""Shared domain models for terminal MCP backends."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel


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


@dataclass(frozen=True, slots=True)
class CapturedSession:
    session: SessionInfo
    content: str
    content_truncated: bool


@dataclass(frozen=True, slots=True)
class TerminalSnapshot:
    sessions: tuple[CapturedSession, ...]
    omitted_session_ids: tuple[str, ...]
    truncated: bool
    default_session_id: str | None
    total: int


class SessionView(BaseModel):
    session_id: str
    name: str
    tty: str | None
    busy: bool
    active: bool
    content: str | None
    content_truncated: bool


class ListSessionsResult(BaseModel):
    sessions: list[SessionView]
    total: int
    active_session_id: str | None


class SetActiveResult(BaseModel):
    success: bool
    session_id: str


class ScreenResult(BaseModel):
    session_id: str
    mode: Literal["focus", "recent-output", "manual"]
    content: str
    lines: int


class AggregateResult(BaseModel):
    session_ids: list[str]
    sessions: list[SessionView]
    default_session_id: str | None
    total: int
    lines: int
    truncated: bool
    omitted_session_ids: list[str]


class WriteResult(BaseModel):
    success: bool
    session_id: str
    executed: bool | None


class ScrollResult(BaseModel):
    session_id: str
    pages: int
    content: str
