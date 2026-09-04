import logging
import os
from dataclasses import dataclass
from os import PathLike
from pathlib import Path

from dotenv import load_dotenv

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def _csv(name: str) -> frozenset[str]:
    return frozenset(
        part.strip() for part in os.getenv(name, "").split(",") if part.strip()
    )


def _ttys(name: str) -> frozenset[str]:
    return frozenset(
        tty if tty.startswith("/dev/") else f"/dev/{tty}" for tty in _csv(name)
    )


def _log_level() -> int:
    value = os.getenv("MCP_TERMINAL_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, value, None)
    return level if isinstance(level, int) else logging.INFO


@dataclass(frozen=True)
class Settings:
    readonly: bool
    excluded_ttys: frozenset[str]
    excluded_sessions: frozenset[str]
    detect_self_session: bool
    allow_self_target: bool
    log_level: int

    @classmethod
    def load(cls, dotenv_path: str | PathLike[str] | None = None) -> "Settings":
        selected_path = (
            Path(dotenv_path)
            if dotenv_path is not None
            else Path(os.getenv("MCP_TERMINAL_ENV_FILE", Path.cwd() / ".env"))
        )
        load_dotenv(dotenv_path=selected_path, override=False)
        return cls(
            readonly=_boolean("MCP_TERMINAL_READONLY", True),
            excluded_ttys=_ttys("MCP_TERMINAL_EXCLUDED_TTYS"),
            excluded_sessions=_csv("MCP_TERMINAL_EXCLUDED_SESSIONS"),
            detect_self_session=_boolean("MCP_TERMINAL_DETECT_SELF_SESSION", True),
            allow_self_target=_boolean("MCP_TERMINAL_ALLOW_SELF_TARGET", False),
            log_level=_log_level(),
        )
