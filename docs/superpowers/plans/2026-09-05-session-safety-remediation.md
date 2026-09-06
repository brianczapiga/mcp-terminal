# Session Safety Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make terminal targeting stable and policy-safe, replace misleading recent-output selection, require deliberate write targets, and align development setup with Python 3.10+ support.

**Architecture:** Keep backend identity generation, manager policy, MCP schema, and development setup as separate changes. Terminal.app will expose TTY-derived IDs while iTerm2 retains native unique IDs; the manager will distinguish configured exclusions from detected self-session state and use explicit resolution rules for reads and writes.

**Tech Stack:** Python 3.10+, FastMCP 3, Pydantic 2, pytest, Ruff, mypy, GNU Make, AppleScript

---

### Task 1: Stabilize Terminal.app Session Identity

**Files:**
- Modify: `terminal_mcp/backends/macos_terminal.py`
- Test: `tests/unit/test_macos_terminal.py`

- [x] **Step 1: Write failing identity tests**

Add tests that call `MacOSTerminalBackend.list_sessions()` with two scans whose
tab indexes are swapped. Assert that each TTY keeps a `terminal_<tty-name>` ID,
and assert that a record without a TTY is omitted. Keep the existing parser test
for iTerm2-style positional IDs unchanged.

```python
def test_terminal_ids_follow_tty_when_tab_indexes_change() -> None:
    first = RecordingRunner("10\t1\tA\t/dev/ttys001\tfalse")
    second = RecordingRunner("10\t2\tA\t/dev/ttys001\tfalse")
    assert (
        MacOSTerminalBackend(first).list_sessions()[0].session_id == "terminal_ttys001"
    )
    assert (
        MacOSTerminalBackend(second).list_sessions()[0].session_id == "terminal_ttys001"
    )


def test_terminal_omits_sessions_without_stable_tty() -> None:
    runner = RecordingRunner("10\t1\tStarting\t\tfalse")
    assert MacOSTerminalBackend(runner).list_sessions() == []
```

- [x] **Step 2: Verify the tests fail**

Run: `.venv/bin/pytest tests/unit/test_macos_terminal.py -q`

Expected: the stable-ID assertion fails with `10_1`, and the missing-TTY record
is still returned.

- [x] **Step 3: Implement TTY-derived Terminal IDs**

Add a backend-local conversion after `_parse_sessions`:

```python
from dataclasses import replace


def _stable_terminal_session(session: SessionInfo) -> SessionInfo | None:
    if session.tty_device is None:
        return None
    tty_name = session.tty_device.removeprefix("/dev/")
    return replace(session, session_id=f"terminal_{tty_name}")
```

Have `MacOSTerminalBackend.list_sessions()` return only converted, non-`None`
sessions. Do not change `_parse_sessions`, because iTerm2's `tab_id` is already a
native unique session ID.

- [x] **Step 4: Verify the backend tests pass**

Run: `.venv/bin/pytest tests/unit/test_macos_terminal.py tests/unit/test_iterm2.py -q`

Expected: all selected tests pass.

### Task 2: Scope the Self-Target Override

**Files:**
- Modify: `terminal_mcp/manager.py`
- Test: `tests/unit/test_manager.py`

- [x] **Step 1: Write failing exclusion-policy tests**

Add separate tests showing that `allow_self_target=True` cannot bypass a
configured session exclusion or configured TTY exclusion, including when the
configured TTY is also the detected controlling TTY. Preserve a test showing
that an explicitly supplied ID can bypass only automatic self detection.

```python
def test_self_override_never_bypasses_configured_exclusions(monkeypatch):
    monkeypatch.setattr(
        "terminal_mcp.manager.detect_controlling_tty", lambda: "/dev/ttys9"
    )
    manager = TerminalManager(
        Backend(
            [
                [
                    session("blocked-id", tty="/dev/ttys1"),
                    session("blocked-tty", tty="/dev/ttys9"),
                ]
            ]
        ),
        settings(
            readonly=False,
            excluded_sessions=frozenset({"blocked-id"}),
            excluded_ttys=frozenset({"/dev/ttys9"}),
            detect_self_session=True,
            allow_self_target=True,
        ),
    )
    with pytest.raises(ExcludedSession):
        manager.send_input("blocked-id", "text")
    with pytest.raises(ExcludedSession):
        manager.send_input("blocked-tty", "text")
```

- [x] **Step 2: Verify the tests fail**

Run: `.venv/bin/pytest tests/unit/test_manager.py -q`

Expected: the new configured-exclusion assertions fail because explicit IDs
currently bypass every exclusion when the override is enabled.

- [x] **Step 3: Separate configured and detected exclusions**

Keep `settings.excluded_ttys` immutable as configured policy and store detected
self TTY in a separate nullable field. Split the checks:

```python
def _is_configured_excluded(self, session: SessionInfo) -> bool:
    return session.session_id in self.settings.excluded_sessions or (
        session.tty_device is not None
        and _normalize_tty(session.tty_device) in self.settings.excluded_ttys
    )


def _is_detected_self(self, session: SessionInfo) -> bool:
    return session.tty_device is not None and self._detected_self_tty == _normalize_tty(
        session.tty_device
    )


def _is_excluded(self, session: SessionInfo) -> bool:
    return self._is_configured_excluded(session) or self._is_detected_self(session)
```

In `_resolve_target`, always reject configured exclusions. Permit a detected
self session only when `session_id` was explicitly supplied and
`allow_self_target` is true.

- [x] **Step 4: Verify manager tests pass**

Run: `.venv/bin/pytest tests/unit/test_manager.py -q`

Expected: all manager tests pass.

### Task 3: Make Read and Write Selection Honest

**Files:**
- Modify: `terminal_mcp/manager.py`
- Modify: `terminal_mcp/models.py`
- Modify: `terminal_mcp/server.py`
- Modify: `README.md`
- Modify: `docs/CLIENTS.md`
- Test: `tests/unit/test_manager.py`
- Test: `tests/contract/test_mcp_contract.py`

- [x] **Step 1: Write failing manager selection tests**

Replace recency assertions with stable automatic selection assertions. Add one
test per write entry point showing that omission of `session_id` without an
active session raises `UnknownSession`, then show that an explicit ID and an
active selection still work.

```python
def test_automatic_selection_is_stable_by_session_id() -> None:
    manager = TerminalManager(Backend([[session("z"), session("a")]]), settings())
    assert manager.automatic_session().session_id == "a"


def test_writes_require_explicit_or_active_target() -> None:
    manager = TerminalManager(Backend([[session("a")]]), settings(readonly=False))
    with pytest.raises(UnknownSession):
        manager.send_input(None, "text")
    manager.set_active_session("a")
    assert manager.send_input(None, "text") == "a"
```

- [x] **Step 2: Write failing MCP schema tests**

Update the contract expectation so `get_screen.mode` accepts `focus`,
`automatic`, and `manual`, and rejects `recent-output`. Assert the write-tool
descriptions or behavior communicates that a target must be explicit or active.

- [x] **Step 3: Verify the selection and contract tests fail**

Run: `.venv/bin/pytest tests/unit/test_manager.py tests/contract/test_mcp_contract.py -q`

Expected: failures mention missing `automatic_session`, accepted
`recent-output`, or automatic write fallback.

- [x] **Step 4: Implement explicit selection rules**

Rename `most_recent_session`/`read_recent_screen` to
`automatic_session`/`read_automatic_screen`. Select with:

```python
return min(sessions, key=lambda item: item.session_id)
```

Add a resolver flag so reads may choose automatically while writes may not:

```python
def _resolve_target(
    self, session_id: str | None, *, allow_automatic: bool = True
) -> SessionInfo:
    explicitly_supplied = session_id is not None
    self.list_sessions()
    if session_id is None:
        session_id = self.active_session_id
    if session_id is None:
        if not allow_automatic:
            raise UnknownSession("Provide session_id or select an active session")
        return self.automatic_session()
    target = self.sessions.get(session_id)
    if target is None:
        raise UnknownSession(f"Unknown terminal session: {session_id}")
    if self._is_configured_excluded(target):
        raise ExcludedSession(f"Terminal session is excluded: {session_id}")
    if self._is_detected_self(target) and not (
        explicitly_supplied and self.settings.allow_self_target
    ):
        raise ExcludedSession(f"Terminal session is excluded: {session_id}")
    return target
```

Call it with `allow_automatic=False` from `send_input`, `send_keypress`, and
`paste_text`.

- [x] **Step 5: Update the MCP schema and documentation**

Change `ScreenMode` and `ScreenResult.mode` to
`Literal["focus", "automatic", "manual"]`. Route `automatic` to
`read_automatic_screen`, retain `focus` as active-or-automatic, and keep
`manual` active-only. Update README and client safety guidance to describe the
write-target requirement and deterministic automatic read behavior.

- [x] **Step 6: Verify selection and contract tests pass**

Run: `.venv/bin/pytest tests/unit/test_manager.py tests/contract/test_mcp_contract.py -q`

Expected: all selected tests pass.

### Task 4: Align `make setup` with Python 3.10+

**Files:**
- Modify: `Makefile`
- Modify: `CONTRIBUTING.md`
- Test: `tests/contract/test_installer.py`

- [x] **Step 1: Write failing Makefile contract tests**

Add tests that confirm `make check-python PYTHON_BIN=<current-python>` succeeds
and that `setup` uses `PYTHON_BIN` instead of hard-coded `python3.12`. Use
`subprocess.run` with `sys.executable`; do not create a venv in the test.

```python
def test_makefile_accepts_supported_configurable_python() -> None:
    result = subprocess.run(
        ["make", "check-python", f"PYTHON_BIN={sys.executable}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
```

- [x] **Step 2: Verify the installer tests fail**

Run: `.venv/bin/pytest tests/contract/test_installer.py -q`

Expected: `make check-python` fails because the target does not exist.

- [x] **Step 3: Add a reusable interpreter check**

Define `PYTHON_BIN ?= python3`, add `check-python` to `.PHONY`, and validate the
interpreter before setup:

```make
PYTHON_BIN ?= python3

check-python:
	@command -v $(PYTHON_BIN) >/dev/null 2>&1 || { echo "$(PYTHON_BIN) is unavailable"; exit 1; }
	@$(PYTHON_BIN) -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' || { echo "Python 3.10 or newer is required"; exit 1; }

setup: check-python
	@if command -v uv >/dev/null 2>&1; then \
		uv venv --python $(PYTHON_BIN) $(VENV); \
		uv pip install --python $(PYTHON) -e '.[dev]'; \
	else \
		$(PYTHON_BIN) -m venv $(VENV); \
		$(PYTHON) -m pip install -e '.[dev]'; \
	fi
```

Document the `PYTHON_BIN` override in `CONTRIBUTING.md`.

- [x] **Step 4: Verify installer tests pass**

Run: `.venv/bin/pytest tests/contract/test_installer.py -q`

Expected: all installer contract tests pass.

### Task 5: Full Verification and Release Notes

**Files:**
- Modify: `CHANGELOG.md`

- [x] **Step 1: Add an Unreleased Fixed section**

Document stable Terminal targeting, strict configured exclusions, explicit
write targets, honest automatic reads, and Python 3.10+ setup alignment under
`[Unreleased]`.

- [x] **Step 2: Run the complete required checks**

Run: `make check`

Expected: Ruff, Ruff formatting, mypy, all non-smoke tests, and both package
artifacts complete successfully.

- [x] **Step 3: Inspect the final diff and status**

Run: `git diff --check && git diff --stat && git status --short`

Expected: no whitespace errors; only the planned implementation, tests,
documentation, changelog, spec, and plan are present.

- [x] **Step 4: Commit the implementation**

```bash
git add terminal_mcp tests Makefile README.md CONTRIBUTING.md docs/CLIENTS.md CHANGELOG.md docs/superpowers/plans/2026-09-05-session-safety-remediation.md
git commit -m "fix: harden terminal session targeting"
```
