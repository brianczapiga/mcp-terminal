import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path

from dotenv import dotenv_values

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _boolean(config: Mapping[str, str | None], name: str, default: bool) -> bool:
    value = config.get(name)
    if value is None:
        return default
    normalized_value = value.strip().lower()
    if normalized_value in TRUE_VALUES:
        return True
    if normalized_value in FALSE_VALUES:
        return False
    return default


def _csv(config: Mapping[str, str | None], name: str) -> frozenset[str]:
    return frozenset(
        part.strip() for part in (config.get(name) or "").split(",") if part.strip()
    )


def _ttys(config: Mapping[str, str | None], name: str) -> frozenset[str]:
    return frozenset(
        tty if tty.startswith("/dev/") else f"/dev/{tty}" for tty in _csv(config, name)
    )


def _log_level(config: Mapping[str, str | None]) -> int:
    value = (config.get("MCP_TERMINAL_LOG_LEVEL") or "INFO").strip().upper()
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
        env_file = os.getenv("MCP_TERMINAL_ENV_FILE")
        if dotenv_path is not None:
            selected_path = Path(dotenv_path)
        elif env_file and env_file.strip():
            selected_path = Path(env_file.strip())
        else:
            selected_path = Path.cwd() / ".env"
        config = dotenv_values(selected_path) | os.environ
        return cls(
            readonly=_boolean(config, "MCP_TERMINAL_READONLY", True),
            excluded_ttys=_ttys(config, "MCP_TERMINAL_EXCLUDED_TTYS"),
            excluded_sessions=_csv(config, "MCP_TERMINAL_EXCLUDED_SESSIONS"),
            detect_self_session=_boolean(
                config, "MCP_TERMINAL_DETECT_SELF_SESSION", True
            ),
            allow_self_target=_boolean(config, "MCP_TERMINAL_ALLOW_SELF_TARGET", False),
            log_level=_log_level(config),
        )
