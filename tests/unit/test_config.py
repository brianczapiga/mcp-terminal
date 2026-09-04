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


@pytest.mark.parametrize("env_file", ["", "   "])
def test_blank_env_file_variable_falls_back_to_cwd_env_file(
    env_file: str, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("MCP_TERMINAL_READONLY=0\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_TERMINAL_ENV_FILE", env_file)

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


def test_sequential_explicit_env_files_are_independent(tmp_path) -> None:
    first_env_file = tmp_path / "first.env"
    first_env_file.write_text("MCP_TERMINAL_READONLY=0\n")
    second_env_file = tmp_path / "second.env"
    second_env_file.write_text("MCP_TERMINAL_READONLY=1\n")

    assert Settings.load(first_env_file).readonly is False
    assert Settings.load(second_env_file).readonly is True


def test_security_defaults() -> None:
    settings = Settings.load()

    assert settings.excluded_sessions == frozenset()
    assert settings.detect_self_session is True
    assert settings.allow_self_target is False


def test_parses_excluded_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TERMINAL_EXCLUDED_SESSIONS", " alpha, , beta ")

    assert Settings.load().excluded_sessions == frozenset({"alpha", "beta"})


@pytest.mark.parametrize("value", ["1", "TRUE", "Yes", "on"])
def test_parses_true_boolean_values(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MCP_TERMINAL_ALLOW_SELF_TARGET", value)

    assert Settings.load().allow_self_target is True


@pytest.mark.parametrize("value", ["0", "false", "NO", "off", "unexpected"])
def test_other_boolean_values_are_false(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MCP_TERMINAL_DETECT_SELF_SESSION", value)

    assert Settings.load().detect_self_session is False


def test_parses_valid_log_level_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_TERMINAL_LOG_LEVEL", "warning")

    assert Settings.load().log_level == logging.WARNING


def test_invalid_log_level_falls_back_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TERMINAL_LOG_LEVEL", "not-a-level")

    assert Settings.load().log_level == logging.INFO


def test_settings_are_immutable() -> None:
    settings = Settings.load()

    with pytest.raises(AttributeError):
        settings.readonly = False
