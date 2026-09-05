# Codex and Claude MCP Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an installable, tested macOS terminal MCP server that works with Codex desktop/CLI and Claude Desktop/Code, defaults to read-only publicly, and enables writes in this checkout through an ignored `.env`.

**Architecture:** Replace the top-level monolith with a `terminal_mcp` package containing configuration, models, terminal backends, session management, and a thin FastMCP server. Inject fake backends for deterministic tests, publish conventional MCP schemas, and retain a compatibility launcher for historical script users.

**Tech Stack:** Python 3.10+, FastMCP 3.x, Pydantic 2, python-dotenv, pytest, pytest-asyncio, Ruff, mypy, PyPA build, GitHub Actions on macOS.

---

## File Structure

- Create `terminal_mcp/__init__.py`: package version exports.
- Create `terminal_mcp/__main__.py`: module execution entry point.
- Create `terminal_mcp/config.py`: environment loading and validated settings.
- Create `terminal_mcp/errors.py`: typed domain failures.
- Create `terminal_mcp/models.py`: session data structures.
- Create `terminal_mcp/backends/base.py`: backend protocol and process runner.
- Create `terminal_mcp/backends/macos_terminal.py`: Terminal.app integration.
- Create `terminal_mcp/backends/iterm2.py`: iTerm2 integration.
- Create `terminal_mcp/backends/detect.py`: application selection.
- Create `terminal_mcp/manager.py`: session policy, selection, and buffers.
- Create `terminal_mcp/server.py`: MCP components and stdio runner.
- Modify `terminal_mcp_server.py`: compatibility launcher only.
- Create focused tests under `tests/unit/`, `tests/contract/`, and `tests/smoke/`.
- Modify packaging, CI, installation scripts, documentation, and examples.

### Task 1: Establish a Reproducible Development Baseline

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt`
- Create: `.python-version`
- Create: `env.example`
- Create locally (ignored): `.env`

- [ ] **Step 1: Confirm `.env` is ignored before creating it**

Run: `git check-ignore -v .env`

Expected: output names the `.env` rule in `.gitignore`.

- [ ] **Step 2: Create the visible safe template and ignored local override**

Apply these exact contents:

```dotenv
# env.example
# Copy this file to .env. Writes are disabled unless explicitly enabled.
MCP_TERMINAL_READONLY=1
MCP_TERMINAL_ENV_FILE=
MCP_TERMINAL_EXCLUDED_TTYS=
MCP_TERMINAL_EXCLUDED_SESSIONS=
MCP_TERMINAL_DETECT_SELF_SESSION=1
MCP_TERMINAL_ALLOW_SELF_TARGET=0
MCP_TERMINAL_LOG_LEVEL=INFO
```

```dotenv
# .env (local and ignored)
MCP_TERMINAL_READONLY=0
```

- [ ] **Step 3: Verify the active file cannot be committed accidentally**

Run: `git status --short --ignored .env env.example`

Expected: `!! .env` and `?? env.example`.

- [ ] **Step 4: Consolidate package and tool metadata**

In `pyproject.toml`, set the runtime dependencies and groups to:

```toml
[project]
requires-python = ">=3.10"
dependencies = [
    "fastmcp>=3.4,<4",
    "pydantic>=2.8,<3",
    "python-dotenv>=1.0,<2",
]

[project.optional-dependencies]
dev = [
    "build>=1.2,<2",
    "mypy>=1.11,<2",
    "pytest>=8.3,<9",
    "pytest-asyncio>=0.24,<2",
    "pytest-cov>=5,<7",
    "ruff>=0.12,<1",
]

[project.scripts]
terminal-mcp-server = "terminal_mcp.server:main"

[tool.setuptools.packages.find]
include = ["terminal_mcp*"]
exclude = ["tests*"]

[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "RUF"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["--strict-markers", "--strict-config", "--tb=short"]
markers = [
    "smoke: requires a real macOS terminal application and permissions",
]
```

Set `.python-version` to `3.12`. Make `requirements.txt` contain `-e .` and
`requirements-dev.txt` contain `-e .[dev]`, keeping `pyproject.toml` as the
single dependency source of truth.

- [ ] **Step 5: Create and install a supported interpreter environment**

Run: `uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e '.[dev]'`

Expected: installation completes and `.venv/bin/python --version` reports
Python 3.12.x. If `uv` is unavailable, install Python 3.12 using the user's
preferred package manager, then run `.venv/bin/python -m pip install -e '.[dev]'`.

- [ ] **Step 6: Commit the baseline**

```bash
git add pyproject.toml requirements.txt requirements-dev.txt .python-version env.example
git commit -m "build: establish modern Python project baseline"
```

### Task 2: Add Typed Configuration with Safe Defaults

**Files:**
- Create: `terminal_mcp/__init__.py`
- Create: `terminal_mcp/config.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write failing configuration tests**

```python
from pathlib import Path

from terminal_mcp.config import Settings


def test_defaults_are_read_only(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MCP_TERMINAL_READONLY", raising=False)
    assert Settings.load().readonly is True


def test_dotenv_enables_local_writes(monkeypatch, tmp_path: Path):
    (tmp_path / ".env").write_text("MCP_TERMINAL_READONLY=0\n")
    monkeypatch.chdir(tmp_path)
    assert Settings.load().readonly is False


def test_process_environment_wins_over_dotenv(monkeypatch, tmp_path: Path):
    (tmp_path / ".env").write_text("MCP_TERMINAL_READONLY=0\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_TERMINAL_READONLY", "1")
    assert Settings.load().readonly is True


def test_csv_exclusions_are_normalized(monkeypatch):
    monkeypatch.setenv("MCP_TERMINAL_EXCLUDED_TTYS", "ttys001, /dev/ttys002")
    settings = Settings.load()
    assert settings.excluded_ttys == frozenset({"/dev/ttys001", "/dev/ttys002"})
```

- [ ] **Step 2: Run tests and verify import failure**

Run: `.venv/bin/pytest tests/unit/test_config.py -q`

Expected: FAIL because `terminal_mcp.config` does not exist.

- [ ] **Step 3: Implement immutable settings**

```python
# terminal_mcp/config.py
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in TRUE_VALUES


def _csv(name: str) -> frozenset[str]:
    return frozenset(
        value.strip() for value in os.getenv(name, "").split(",") if value.strip()
    )


def _tty(value: str) -> str:
    return value if value.startswith("/dev/") else f"/dev/{value}"


@dataclass(frozen=True)
class Settings:
    readonly: bool
    excluded_ttys: frozenset[str]
    excluded_sessions: frozenset[str]
    detect_self_session: bool
    allow_self_target: bool
    log_level: int

    @classmethod
    def load(cls, dotenv_path: Path | None = None) -> "Settings":
        configured_path = os.getenv("MCP_TERMINAL_ENV_FILE")
        selected_path = dotenv_path or (
            Path(configured_path) if configured_path else Path.cwd() / ".env"
        )
        load_dotenv(dotenv_path=selected_path, override=False)
        level_name = os.getenv("MCP_TERMINAL_LOG_LEVEL", "INFO").upper()
        return cls(
            readonly=_bool("MCP_TERMINAL_READONLY", True),
            excluded_ttys=frozenset(
                _tty(value) for value in _csv("MCP_TERMINAL_EXCLUDED_TTYS")
            ),
            excluded_sessions=_csv("MCP_TERMINAL_EXCLUDED_SESSIONS"),
            detect_self_session=_bool("MCP_TERMINAL_DETECT_SELF_SESSION", True),
            allow_self_target=_bool("MCP_TERMINAL_ALLOW_SELF_TARGET", False),
            log_level=getattr(logging, level_name, logging.INFO),
        )
```

Set `terminal_mcp/__init__.py` to `__version__ = "2.0.0"` and update the
project version to the same value.

- [ ] **Step 4: Run the focused tests**

Run: `.venv/bin/pytest tests/unit/test_config.py -q`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add terminal_mcp pyproject.toml tests/unit/test_config.py
git commit -m "feat: add safe terminal MCP configuration"
```

### Task 3: Define Models, Errors, and Backend Boundary

**Files:**
- Create: `terminal_mcp/errors.py`
- Create: `terminal_mcp/models.py`
- Create: `terminal_mcp/backends/__init__.py`
- Create: `terminal_mcp/backends/base.py`
- Create: `tests/unit/test_backend_base.py`

- [ ] **Step 1: Write failing process-runner tests**

```python
from unittest.mock import Mock, patch

import pytest

from terminal_mcp.backends.base import AppleScriptRunner
from terminal_mcp.errors import AutomationDenied, ScriptFailed, ScriptTimedOut


def test_runner_returns_text():
    completed = Mock(returncode=0, stdout="result\n", stderr="")
    with patch("subprocess.run", return_value=completed):
        assert AppleScriptRunner().run("return 1") == "result"


@pytest.mark.parametrize(
    ("stderr", "error_type"),
    [
        ("Not authorized to send Apple events", AutomationDenied),
        ("syntax error", ScriptFailed),
    ],
)
def test_runner_classifies_failures(stderr, error_type):
    completed = Mock(returncode=1, stdout="", stderr=stderr)
    with patch("subprocess.run", return_value=completed), pytest.raises(error_type):
        AppleScriptRunner().run("bad script")


def test_runner_classifies_timeout():
    with (
        patch("subprocess.run", side_effect=TimeoutError),
        pytest.raises(ScriptTimedOut),
    ):
        AppleScriptRunner().run("slow script")
```

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/pytest tests/unit/test_backend_base.py -q`

Expected: FAIL because the backend boundary is absent.

- [ ] **Step 3: Implement the domain types**

Define `TerminalMcpError`, `ApplicationUnavailable`, `AutomationDenied`,
`ScriptTimedOut`, `ScriptFailed`, `MalformedResponse`, `UnknownSession`,
`ExcludedSession`, and `WriteDisabled` in `errors.py`. Define this immutable
session model in `models.py`:

```python
@dataclass(frozen=True, slots=True)
class SessionInfo:
    session_id: str
    window_id: str
    tab_id: str
    name: str
    tty_device: str | None
    is_busy: bool
    observed_at: float
```

Define a `TerminalBackend` protocol with `name`, `list_sessions()`,
`read_screen(session, lines)`, `send_text(session, text, execute)`,
`send_keypress(session, key, modifiers)`, and `paste_text(session, text)`.
Implement `AppleScriptRunner.run()` with `text=True`, a ten-second timeout,
stderr-only logging, and the error classification asserted above. Catch
`subprocess.TimeoutExpired` as well as the test's `TimeoutError`.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/unit/test_backend_base.py -q`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add terminal_mcp/errors.py terminal_mcp/models.py terminal_mcp/backends tests/unit/test_backend_base.py
git commit -m "refactor: define terminal backend boundary"
```

### Task 4: Extract and Test Terminal.app and iTerm2 Backends

**Files:**
- Create: `terminal_mcp/backends/macos_terminal.py`
- Create: `terminal_mcp/backends/iterm2.py`
- Create: `terminal_mcp/backends/detect.py`
- Create: `tests/unit/test_macos_terminal.py`
- Create: `tests/unit/test_iterm2.py`
- Create: `tests/unit/test_backend_detection.py`

- [ ] **Step 1: Write parsing and detection tests using representative fixtures**

```python
def test_terminal_parses_one_session(runner):
    runner.run.return_value = "75081\t1\tBuild\t/dev/ttys001\tfalse"
    sessions = MacOSTerminalBackend(runner).list_sessions()
    assert sessions[0].session_id == "75081_1"
    assert sessions[0].tty_device == "/dev/ttys001"


def test_iterm_parses_one_session(runner):
    runner.run.return_value = "w-1\ts-1\tAPI\t/dev/ttys004\ttrue"
    sessions = ITerm2Backend(runner).list_sessions()
    assert sessions[0].session_id == "w-1_s-1"


def test_detect_prefers_running_iterm(runner):
    runner.run.side_effect = ["iTerm2", "iTerm2"]
    assert detect_backend(runner).name == "iTerm2"
```

Also test empty output, a field containing commas, missing values, malformed
rows, content line limiting, write AppleScript escaping, and detection fallback
to Terminal.app.

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/pytest tests/unit/test_macos_terminal.py tests/unit/test_iterm2.py tests/unit/test_backend_detection.py -q`

Expected: FAIL because concrete backends do not exist.

- [ ] **Step 3: Implement delimiter-safe backends**

Move the application-specific behavior out of `terminal_mcp_server.py`. Make
each AppleScript emit one session per line with tab-separated fields. Reject
rows with fewer than five fields using `MalformedResponse`; do not manufacture
a fake `1_1` session. Keep all escaping in a shared helper:

```python
def applescript_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
```

Construct `SessionInfo` with `time.time()` supplied through an injectable clock.
Keep write operations scoped to the exact window/tab or iTerm session IDs.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/unit/test_macos_terminal.py tests/unit/test_iterm2.py tests/unit/test_backend_detection.py -q`

Expected: all backend tests pass.

- [ ] **Step 5: Commit**

```bash
git add terminal_mcp/backends tests/unit/test_macos_terminal.py tests/unit/test_iterm2.py tests/unit/test_backend_detection.py
git commit -m "refactor: isolate macOS terminal backends"
```

### Task 5: Implement Session Management and Self-Session Protection

**Files:**
- Create: `terminal_mcp/manager.py`
- Create: `tests/unit/test_manager.py`
- Create: `tests/unit/test_self_session.py`

- [ ] **Step 1: Write failing manager policy tests**

```python
def test_list_sessions_excludes_configured_tty(manager, backend):
    backend.list_sessions.return_value = [
        session("a", "/dev/ttys001"),
        session("b", "/dev/ttys002"),
    ]
    manager.excluded_ttys = frozenset({"/dev/ttys001"})
    assert [item.session_id for item in manager.list_sessions()] == ["b"]


def test_stale_sessions_are_removed(manager, backend):
    backend.list_sessions.side_effect = [[session("a")], [session("b")]]
    assert [item.session_id for item in manager.list_sessions(force=True)] == ["a"]
    assert [item.session_id for item in manager.list_sessions(force=True)] == ["b"]


def test_excluded_session_cannot_be_targeted(manager):
    manager.excluded_sessions = frozenset({"a"})
    with pytest.raises(ExcludedSession):
        manager.set_active_session("a")


def test_write_policy_is_centralized(readonly_manager):
    with pytest.raises(WriteDisabled):
        readonly_manager.send_input("a", "pwd", execute=True)
```

Add process tests that parse `ps -o tty= -p <pid>` output, walk parents until a
TTY is found, normalize `ttys003` to `/dev/ttys003`, and return `None` without
raising when GUI-launched processes have `??` or empty TTYs.

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/pytest tests/unit/test_manager.py tests/unit/test_self_session.py -q`

Expected: FAIL because the manager is absent.

- [ ] **Step 3: Implement the manager**

Implement `TerminalManager(backend, settings, clock=time.monotonic)` with a
two-second scan cache. Replace the entire session map on each real scan, apply
session/TTY exclusions before caching, and choose the most recently observed
eligible session only when no valid active session exists. Put the read-only
check in `_require_write()` and call it from all four write methods.

Implement `detect_controlling_tty(pid=os.getpid()) -> str | None` using bounded
parent traversal (maximum 32 parents) and `ps -o tty= -o ppid= -p PID`. Merge a
detected TTY into configured exclusions only when
`settings.detect_self_session` is true. Honor `allow_self_target` only for an
explicit session ID; automatic selection must always skip excluded sessions.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/unit/test_manager.py tests/unit/test_self_session.py -q`

Expected: all manager tests pass.

- [ ] **Step 5: Commit**

```bash
git add terminal_mcp/manager.py tests/unit/test_manager.py tests/unit/test_self_session.py
git commit -m "feat: protect terminal session selection"
```

### Task 6: Publish a Conventional MCP Contract

**Files:**
- Create: `terminal_mcp/server.py`
- Create: `terminal_mcp/__main__.py`
- Replace: `terminal_mcp_server.py`
- Create: `tests/contract/test_mcp_contract.py`

- [ ] **Step 1: Write failing MCP discovery tests**

Use FastMCP's in-memory client transport:

```python
@pytest.mark.asyncio
async def test_tool_schemas_have_no_legacy_request(fake_server):
    async with Client(fake_server) as client:
        tools = await client.list_tools()
    assert {tool.name for tool in tools} >= {
        "list_sessions",
        "set_active_session",
        "get_screen",
        "get_all_terminal_info",
        "send_input",
        "send_keypress",
        "paste_text",
        "scroll_back",
    }
    assert all(
        "request" not in tool.inputSchema.get("properties", {}) for tool in tools
    )


@pytest.mark.asyncio
async def test_send_input_returns_structured_success(fake_server):
    async with Client(fake_server) as client:
        result = await client.call_tool(
            "send_input", {"session_id": "a", "text": "pwd"}
        )
    assert result.structured_content == {"success": True, "session_id": "a"}


@pytest.mark.asyncio
async def test_readonly_write_is_a_tool_error(readonly_server):
    async with Client(readonly_server) as client:
        result = await client.call_tool(
            "send_input", {"session_id": "a", "text": "pwd"}
        )
    assert result.is_error
    assert "disabled" in result.content[0].text.lower()
```

Also verify the session resource template, prompt discovery, `lines` bounds
(1..500), `pages` bounds (1..20), and a literal mode type containing `focus`,
`recent-output`, and `manual`.

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/pytest tests/contract/test_mcp_contract.py -q`

Expected: FAIL because the new server factory does not exist.

- [ ] **Step 3: Implement an injectable server factory**

Implement `create_server(manager: TerminalManager) -> FastMCP` and register thin
functions whose signatures expose only real inputs. Use `Annotated[int,
Field(ge=1, le=500)]` for lines, `Annotated[int, Field(ge=1, le=20)]` for pages,
and `Literal[...]` for mode. Translate domain failures into FastMCP-supported
tool errors. Return dictionaries with stable keys; do not return error text as
normal content.

Implement `main()` as:

```python
def main() -> None:
    settings = Settings.load()
    logging.basicConfig(level=settings.log_level, stream=sys.stderr)
    runner = AppleScriptRunner()
    manager = TerminalManager(detect_backend(runner), settings)
    create_server(manager).run(transport="stdio")
```

Make `terminal_mcp/__main__.py` call `main()`. Replace the old top-level file
with imports that re-export `TerminalManager`, `SessionInfo`, `create_server`,
and `main`, followed by the normal `if __name__ == "__main__": main()` guard.

- [ ] **Step 4: Run contract and unit tests**

Run: `.venv/bin/pytest tests/unit tests/contract -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add terminal_mcp terminal_mcp_server.py tests/contract/test_mcp_contract.py
git commit -m "feat: publish modern MCP tool contract"
```

### Task 7: Verify the Distributable Package

**Files:**
- Create: `tests/contract/test_packaging.py`
- Modify: `Makefile`
- Modify: `install.sh`

- [ ] **Step 1: Write a failing wheel-content test**

```python
def test_wheel_contains_server_module(tmp_path):
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
        check=True,
    )
    wheel = next(tmp_path.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    assert "terminal_mcp/server.py" in names
    assert any(name.endswith(".dist-info/entry_points.txt") for name in names)
```

- [ ] **Step 2: Run the test and verify the packaging gap**

Run: `.venv/bin/pytest tests/contract/test_packaging.py -q`

Expected before package metadata is complete: FAIL; after Task 6's package is
included correctly, this may pass immediately, which confirms the regression is
covered.

- [ ] **Step 3: Modernize developer commands and installer**

Make `setup` create `.venv`, install `-e '.[dev]'`, and never use the old
`venv/` path. Make `check` run, in order:

```make
check:
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .
	.venv/bin/mypy terminal_mcp tests
	.venv/bin/pytest -m "not smoke"
	.venv/bin/python -m build
```

Update `install.sh` to require Python 3.10+, create `.venv`, install the project
itself, copy `env.example` to `.env` only when `.env` does not already exist,
and print that writes remain disabled until the user edits `.env`.

- [ ] **Step 4: Build and inspect a clean wheel**

Run: `.venv/bin/python -m build && .venv/bin/pytest tests/contract/test_packaging.py -q`

Expected: sdist and wheel build successfully; packaging test passes.

- [ ] **Step 5: Commit**

```bash
git add tests/contract/test_packaging.py Makefile install.sh
git commit -m "build: verify installable terminal MCP package"
```

### Task 8: Add Codex and Claude Client Configuration

**Files:**
- Create: `examples/codex-config.toml`
- Create: `examples/claude-desktop-config.json`
- Create: `docs/CLIENTS.md`
- Modify: `examples/goose_config.json`
- Modify: `examples/void_config.yaml`

- [ ] **Step 1: Add a documentation contract test**

Create `tests/contract/test_documentation.py` that parses JSON and TOML examples,
asserts every primary example launches `terminal-mcp-server`, asserts Codex uses
an `[mcp_servers.terminal]` table, and asserts no example uses `PYTHONPATH` or
invokes `terminal_mcp_server.py`.

- [ ] **Step 2: Run the test and verify failure**

Run: `.venv/bin/pytest tests/contract/test_documentation.py -q`

Expected: FAIL because modern client examples are missing.

- [ ] **Step 3: Add client examples and instructions**

Use this Codex example, replacing the command with an absolute installed path
when documenting a virtualenv checkout:

```toml
[mcp_servers.terminal]
command = "/absolute/path/to/mcp-terminal/.venv/bin/terminal-mcp-server"
startup_timeout_sec = 20
tool_timeout_sec = 30
env = { MCP_TERMINAL_ENV_FILE = "/absolute/path/to/mcp-terminal/.env" }
```

Use this Claude Desktop server entry:

```json
{
  "mcpServers": {
    "terminal": {
      "command": "/absolute/path/to/mcp-terminal/.venv/bin/terminal-mcp-server",
      "args": [],
      "env": {
        "MCP_TERMINAL_ENV_FILE": "/absolute/path/to/mcp-terminal/.env"
      }
    }
  }
}
```

Document the current Claude Code registration form after verifying it against
the installed `claude mcp add --help`; show both local/project scope and user
scope where supported. Explain that Codex desktop and CLI read the same Codex
configuration, that `MCP_TERMINAL_ENV_FILE` gives GUI-launched clients a stable
absolute path to `.env`, and that clients may enforce
`MCP_TERMINAL_READONLY=1` explicitly. Keep Goose/Void
examples only as clearly secondary supported configurations and remove their
request-wrapper claims.

- [ ] **Step 4: Validate examples**

Run: `.venv/bin/pytest tests/contract/test_documentation.py -q`

Expected: all documentation contract tests pass.

- [ ] **Step 5: Commit**

```bash
git add examples docs/CLIENTS.md tests/contract/test_documentation.py
git commit -m "docs: add Codex and Claude MCP setup"
```

### Task 9: Correct User and Contributor Documentation

**Files:**
- Modify: `README.md`
- Modify: `QUICKSTART.md`
- Modify: `CONTRIBUTING.md`
- Modify: `CHANGELOG.md`
- Modify: `health_check.py`
- Create: `tests/unit/test_health_check.py`

- [ ] **Step 1: Extend documentation checks for known drift**

Assert that public docs contain no `Python 3.8`, `curl
http://localhost:8000/health`, `System Preferences`, or claims that tests may
fail. Assert they mention `env.example`, `.env`, Codex desktop, Claude Desktop,
and Claude Code.

- [ ] **Step 2: Run the checks and verify failure**

Run: `.venv/bin/pytest tests/contract/test_documentation.py -q`

Expected: FAIL on the known stale text.

- [ ] **Step 3: Rewrite the documentation around the supported workflow**

Make the quick path: Python 3.10+, `make setup`, `cp env.example .env`, choose
read/write policy, install the client configuration, run `make health`, then
connect. Use “System Settings → Privacy & Security → Automation/Accessibility”
for current macOS. Remove the HTTP health endpoint. Describe self-session
exclusion as best-effort and explain the override variables.

Move the changelog's unreleased content above released versions and add a
`2.0.0` section covering package layout, modern MCP schemas, Codex/Claude setup,
safe defaults, and removal of the Void request wrapper.

- [ ] **Step 4: Make health checks side-effect free**

Test and change `health_check.py` so importing/initializing the server does not
launch or activate Terminal/iTerm2. Check dependency versions, package import,
supported Python, macOS, `osascript` availability, and effective read-only mode.
Report permissions as guidance unless a real AppleScript check proves denial.

- [ ] **Step 5: Run documentation and health tests**

Run: `.venv/bin/pytest tests/unit/test_health_check.py tests/contract/test_documentation.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add README.md QUICKSTART.md CONTRIBUTING.md CHANGELOG.md health_check.py tests
git commit -m "docs: align setup and health guidance"
```

### Task 10: Make CI Enforce the Contract

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add a static CI regression assertion**

Extend `tests/contract/test_documentation.py` to assert the workflow contains no
`continue-on-error: true`, no `|| echo`, uses current major versions of
`actions/setup-python` and `actions/cache`, and runs `make check`.

- [ ] **Step 2: Run the assertion and verify failure**

Run: `.venv/bin/pytest tests/contract/test_documentation.py -q`

Expected: FAIL on the existing permissive workflow.

- [ ] **Step 3: Replace permissive CI with mandatory jobs**

Use macOS with Python 3.10, 3.11, 3.12, and 3.13. Install `.[dev]`; run Ruff,
mypy, non-smoke tests, and build the artifact. Add a clean-wheel job that
installs only the built wheel in a fresh environment and runs:

```bash
terminal-mcp-server --help || test $? -ne 127
python -c "import terminal_mcp.server"
```

Do not swallow test or security failures. Upload reports only with
`if: always()` and keep report generation separate from pass/fail status.

- [ ] **Step 4: Run the complete local equivalent**

Run: `make check`

Expected: lint, formatting, typing, tests, and package build all pass.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml tests/contract/test_documentation.py
git commit -m "ci: enforce tests and package verification"
```

### Task 11: Perform Real Client Smoke Tests and Release Verification

**Files:**
- Create: `tests/smoke/test_real_terminal.py`
- Modify: `docs/CLIENTS.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add an opt-in macOS smoke test**

Write a `@pytest.mark.smoke` test that loads settings, detects a backend, lists
sessions, asserts the list does not contain the detected controlling TTY, and
reads at most ten lines from an eligible session. It must skip with an explicit
reason when no terminal, session, or permission is available. Do not write to a
real terminal in the automated smoke test.

- [ ] **Step 2: Run the deterministic suite**

Run: `.venv/bin/pytest -m "not smoke" -q`

Expected: all tests pass.

- [ ] **Step 3: Run the real read-only smoke test**

Run: `MCP_TERMINAL_READONLY=1 .venv/bin/pytest -m smoke -v`

Expected: PASS with an available authorized terminal or a documented SKIP.

- [ ] **Step 4: Verify each installed client manually**

For Codex desktop, Codex CLI, Claude Desktop, and Claude Code:

1. Install the example using the absolute `.venv/bin/terminal-mcp-server` path.
2. Restart or open a new client session.
3. Confirm all eight tools are discovered without a `request` property.
4. Call `list_sessions` and `get_screen`.
5. With this checkout's `.env`, send a harmless `printf 'mcp-smoke-test\\n'`
   command to a deliberately selected non-client terminal.
6. Set the client environment to `MCP_TERMINAL_READONLY=1` and confirm the same
   write is rejected.
7. In Claude Code, confirm its hosting TTY is absent when detection succeeds.

Record the tested client versions and date in `docs/CLIENTS.md`. If a client is
not installed, mark that manual check as pending rather than claiming support
from automated tests alone.

- [ ] **Step 5: Run final verification**

Run: `git status --short && git check-ignore -v .env && make check`

Expected: `.env` remains ignored; only intentional documentation changes are
uncommitted before the final commit; all checks pass.

- [ ] **Step 6: Commit final smoke-test documentation**

```bash
git add tests/smoke/test_real_terminal.py docs/CLIENTS.md CHANGELOG.md
git commit -m "test: verify macOS MCP client integration"
```

## Final Review Checklist

- [ ] Compare every acceptance criterion in the design specification with a
  passing automated test or recorded manual client check.
- [ ] Confirm `git ls-files .env` prints nothing and `git ls-files env.example`
  prints `env.example`.
- [ ] Inspect the built wheel to confirm it includes all `terminal_mcp` modules
  and console entry-point metadata.
- [ ] Confirm no logs, terminal content, or protocol diagnostics are written to
  stdout during stdio operation.
- [ ] Confirm the public no-variable default rejects all four write operations.
- [ ] Confirm this checkout's ignored `.env` enables all four write operations.
- [ ] Confirm Codex and Claude tool discovery publishes concise conventional
  schemas without legacy client wrapper fields.
