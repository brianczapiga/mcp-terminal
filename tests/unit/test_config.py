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


def test_safe_defaults_without_env_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    value = Settings.load()
    assert value.readonly is True
    assert value.excluded_sessions == frozenset()
    assert value.detect_self_session is True
    assert value.allow_self_target is False


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


def test_sequential_explicit_env_files_are_independent(tmp_path) -> None:
    first_env_file = tmp_path / "first.env"
    first_env_file.write_text("MCP_TERMINAL_READONLY=0\n")
    second_env_file = tmp_path / "second.env"
    second_env_file.write_text("MCP_TERMINAL_READONLY=1\n")

    assert Settings.load(first_env_file).readonly is False
    assert Settings.load(second_env_file).readonly is True


@pytest.mark.parametrize(
    ("variable", "attribute", "value", "expected"),
    [
        ("MCP_TERMINAL_ALLOW_SELF_TARGET", "allow_self_target", "1", True),
        ("MCP_TERMINAL_ALLOW_SELF_TARGET", "allow_self_target", "Yes", True),
        ("MCP_TERMINAL_DETECT_SELF_SESSION", "detect_self_session", "0", False),
        ("MCP_TERMINAL_DETECT_SELF_SESSION", "detect_self_session", "NO", False),
        ("MCP_TERMINAL_READONLY", "readonly", "unexpected", True),
        ("MCP_TERMINAL_DETECT_SELF_SESSION", "detect_self_session", "", True),
        ("MCP_TERMINAL_ALLOW_SELF_TARGET", "allow_self_target", "   ", False),
    ],
)
def test_boolean_parsing_and_malformed_defaults(
    variable: str,
    attribute: str,
    value: str,
    expected: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(variable, value)

    assert getattr(Settings.load(), attribute) is expected
