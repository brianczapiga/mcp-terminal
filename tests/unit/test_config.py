import logging
import os
from collections.abc import Iterator

import pytest

from terminal_mcp.config import Settings

ENVIRONMENT_VARIABLES = (
    "MCP_TERMINAL_READONLY",
    "MCP_TERMINAL_EXCLUDED_TTYS",
    "MCP_TERMINAL_EXCLUDED_SESSIONS",
    "MCP_TERMINAL_DETECT_SELF_SESSION",
    "MCP_TERMINAL_ALLOW_SELF_TARGET",
    "MCP_TERMINAL_LOG_LEVEL",
    "MCP_TERMINAL_ENV_FILE",
)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for variable in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    yield
    for variable in ENVIRONMENT_VARIABLES:
        os.environ.pop(variable, None)


def test_defaults_to_readonly_without_env_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert Settings.load().readonly is True


def test_loads_readonly_from_cwd_env_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("MCP_TERMINAL_READONLY=0\n")
    monkeypatch.chdir(tmp_path)

    assert Settings.load().readonly is False


def test_process_environment_takes_precedence_over_env_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("MCP_TERMINAL_READONLY=0\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_TERMINAL_READONLY", "1")

    assert Settings.load().readonly is True


def test_normalizes_excluded_ttys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TERMINAL_EXCLUDED_TTYS", "ttys001, /dev/ttys002")

    assert Settings.load().excluded_ttys == frozenset({"/dev/ttys001", "/dev/ttys002"})


def test_env_file_variable_overrides_cwd_env_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / ".env").write_text("MCP_TERMINAL_READONLY=1\n")
    selected_env_file = tmp_path / "selected.env"
    selected_env_file.write_text("MCP_TERMINAL_READONLY=0\n")
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("MCP_TERMINAL_ENV_FILE", str(selected_env_file))

    assert Settings.load().readonly is False


def test_explicit_env_file_overrides_env_file_variable(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected_env_file = tmp_path / "selected.env"
    selected_env_file.write_text("MCP_TERMINAL_READONLY=1\n")
    explicit_env_file = tmp_path / "explicit.env"
    explicit_env_file.write_text("MCP_TERMINAL_READONLY=0\n")
    monkeypatch.setenv("MCP_TERMINAL_ENV_FILE", str(selected_env_file))

    assert Settings.load(explicit_env_file).readonly is False


def test_invalid_log_level_falls_back_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TERMINAL_LOG_LEVEL", "not-a-level")

    assert Settings.load().log_level == logging.INFO


def test_settings_are_immutable() -> None:
    settings = Settings.load()

    with pytest.raises(AttributeError):
        settings.readonly = False
