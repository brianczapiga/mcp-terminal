# Session Safety Remediation Design

## Objective

Correct four issues found during the v2.0.0 repository review: unstable
Terminal.app session identities, an overly broad self-target override,
misleading recent-output selection, and a Python-version mismatch in the
recommended development setup.

The changes prioritize reliable write targeting. Compatibility with the v2.0.0
tool schema is secondary because the project currently has one user.

## Session Identity

Terminal.app tab indexes change when tabs are reordered, so the current
`<window-id>_<tab-index>` session ID can silently identify a different TTY after
a rescan. Terminal.app sessions will instead use their TTY as the stable part of
the public identifier. The identifier will use a readable, URI-safe form such as
`terminal_ttys004`; the backend will continue resolving each operation by exact
window ID and TTY at execution time.

Terminal.app tabs without a TTY cannot be targeted safely by the existing
backend and will not be published as eligible sessions. iTerm2 will retain its
native unique-session-ID identity. Manager state and screen buffers will remain
keyed by public session ID, so a tab reorder preserves the correct selection and
buffer rather than transferring them to another tab.

## Exclusion Policy

Configured exclusions and automatic self-session detection will be represented
separately:

- `MCP_TERMINAL_EXCLUDED_SESSIONS` and `MCP_TERMINAL_EXCLUDED_TTYS` are absolute
  denials for listing, selection, reads, and writes.
- The automatically detected controlling TTY is hidden and denied by default.
- `MCP_TERMINAL_ALLOW_SELF_TARGET=1` permits an explicitly supplied session ID
  to bypass only the automatic self-session denial.
- The override never bypasses either configured exclusion, even when the same
  TTY is also detected as the server's controlling TTY.
- Implicit or active-session resolution never uses the self-target override.

## Selection Semantics

The server cannot observe when output was produced across arbitrary terminal
tabs without continuously polling their contents. The `recent-output` mode
therefore promises behavior the backend cannot reliably provide. It will be
replaced by `automatic`.

`automatic` reads the active session when one has been selected. Without an
active session, it chooses the first eligible session in stable session-ID
order. `focus` keeps the same selection behavior as an alias for compatibility,
while `manual` continues to require an active session. Documentation and tool
descriptions will describe these rules without claiming recency.

All three write tools will reject calls that omit `session_id` when no active
session has been selected. They will no longer fall back to any automatically
chosen session. An explicit `session_id` remains sufficient; callers may also
call `set_active_session` before a write.

## Development Setup

`make setup` will use a configurable `PYTHON_BIN` interpreter, defaulting to
`python3`. It will validate that interpreter as Python 3.10 or newer before
creating `.venv`. When `uv` is available it will receive that interpreter;
otherwise the same interpreter will create the venv directly. This aligns the
Makefile with `pyproject.toml`, `install.sh`, and the README.

The contributor documentation will explain `PYTHON_BIN=python3.11 make setup`
for systems where the desired interpreter is not named `python3`.

## Error Handling

Missing write targets will raise `UnknownSession` with a message that tells the
caller to provide `session_id` or select an active session. Existing MCP error
sanitization will convert this to the public unavailable-session tool error.
Terminal.app sessions without a stable TTY will be omitted instead of appearing
in listings and failing only when used.

## Testing

Regression tests will cover:

- Terminal.app IDs remaining bound to the same TTY when tab indexes swap.
- Missing-TTY Terminal.app records being omitted while iTerm2 parsing remains
  unchanged.
- Configured exclusions remaining absolute with the self-target override on.
- The override allowing only an explicit automatically detected self-session.
- Writes requiring an explicit or active target.
- Stable automatic read selection and removal of the recent-output schema value.
- Makefile setup accepting a supported configurable interpreter and rejecting an
  unsupported one through a small testable version-check helper.

The complete Ruff, formatting, mypy, non-smoke pytest, and package-build checks
must pass. The real-terminal smoke test remains opt-in because it requires a
running macOS terminal and user-granted permissions.
