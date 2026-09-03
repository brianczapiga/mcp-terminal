# Codex and Claude MCP Modernization Design

## Objective

Modernize Terminal MCP Server so it works reliably as a local stdio MCP server
with the macOS Codex desktop app, Codex CLI, Claude Desktop, and Claude Code.
Codex desktop is the primary target. Claude Desktop, Codex CLI, and Claude Code
are required compatibility targets.

The modernization must preserve read/write terminal control for this checkout
while making the public repository safe by default.

## Current-State Findings

The repository has several forms of drift that prevent treating the current
release as a reliable client integration:

- The public package requires Python 3.10, while `install.sh`, `QUICKSTART.md`,
  and `CONTRIBUTING.md` claim Python 3.8 support.
- The package discovery configuration is aimed at packages even though the
  implementation is a single top-level module, so a built wheel may omit the
  server module.
- CI explicitly continues when tests fail.
- Unit tests do not consistently model `subprocess.run(..., text=True)` and do
  not exercise MCP discovery or calls through an MCP client.
- Tool schemas contain a legacy `request` compatibility argument on every
  tool. That exposes client-specific transport workarounds to modern clients.
- Documentation describes an HTTP health endpoint although the server runs
  over stdio and only provides a standalone health-check script.
- The server implementation combines MCP registration, session policy,
  AppleScript generation, parsing, process execution, and caching in one large
  module.
- Client examples cover older Goose and Void configuration patterns but not
  the required Codex and Claude interfaces.

## Chosen Approach

Perform a compatibility-focused refactor while retaining FastMCP. This is
preferred over a narrow patch because terminal backends and MCP behavior need
independent tests. It is preferred over a rewrite on the lower-level official
MCP SDK because FastMCP's conventional tool, resource, prompt, and stdio APIs
remain suitable for this server.

FastMCP will be constrained to a tested stable major-version range instead of
the current unbounded `fastmcp>=2.0.0` dependency. The exact supported range
will be selected during implementation after running the compatibility suite
against current releases.

## Architecture

The installable code will become a real `terminal_mcp` package:

- `terminal_mcp/config.py` loads configuration and applies safe defaults.
- `terminal_mcp/models.py` defines session and response data structures.
- `terminal_mcp/backends/base.py` defines the terminal backend interface.
- `terminal_mcp/backends/macos_terminal.py` owns Terminal.app AppleScript and
  response parsing.
- `terminal_mcp/backends/iterm2.py` owns iTerm2 AppleScript and response
  parsing.
- `terminal_mcp/manager.py` owns session discovery, selection, buffers, and
  self-session exclusion.
- `terminal_mcp/server.py` registers MCP tools, resources, and prompts.
- `terminal_mcp/__main__.py` provides the stdio entry point.

The existing `terminal-mcp-server` console command will remain the supported
launch interface. A lightweight compatibility module may remain at
`terminal_mcp_server.py` if needed for users invoking the historical script,
but new documentation and client configurations will use the installed console
command.

## MCP Interface

The server will expose conventional typed FastMCP functions. Parameters will be
the actual tool inputs; legacy per-tool `request` wrapper parameters will not
appear in published schemas.

The initial tool set remains behaviorally focused:

- `list_sessions`
- `set_active_session`
- `get_screen`
- `get_all_terminal_info`
- `send_input`
- `send_keypress`
- `paste_text`
- `scroll_back`

Tool descriptions will be concise and will state side effects, write safety,
and important selection behavior. Input ranges and enumerated modes will be
validated at the schema boundary. Tool outputs will use stable structured
shapes rather than mixing normal results with error-like strings.

Resources and prompts will be retained only where they provide distinct value
and pass discovery/call tests in the supported clients. Prompts will return
useful templates rather than a short acknowledgement that discards their
documented content.

## Configuration and Safety

The code-level default is:

```dotenv
MCP_TERMINAL_READONLY=1
```

The committed, visible template will be named `env.example` with no leading
dot. It will document the safe repository default and all supported variables.
The active local file remains `.env`, is ignored by Git, and for this checkout
will contain:

```dotenv
MCP_TERMINAL_READONLY=0
```

Configuration loading will use `.env` without overriding environment variables
explicitly supplied by a client or shell. Consequently, managed deployments
can always enforce read-only operation regardless of a checkout's local file.

The implementation and automated checks will preserve the `.env` entry in
`.gitignore`. Documentation will tell users to copy `env.example` to `.env` and
make a deliberate choice before enabling writes.

Write tools will enforce the effective setting in one shared policy layer.
Read operations remain available in both modes.

## Self-Session Protection

Claude Code can launch the server from a terminal that the server itself can
observe. Reading and writing that same session can create a feedback loop in
which the client treats its own conversation or command output as external
state.

At startup, the server will attempt to identify its controlling TTY by
inspecting its process context and ancestry. When identified, the corresponding
terminal session will be excluded from automatic selection and aggregate
session results.

Self-session detection is best-effort. GUI clients such as Codex desktop and
Claude Desktop may start the stdio server without a controlling TTY. Failure to
identify one must not prevent startup or hide unrelated sessions.

Configuration will support:

- additional excluded TTYs or session identifiers;
- disabling automatic self-session exclusion for intentional observation; and
- an explicit opt-in for targeting an excluded session.

An attempt to target an excluded session without opt-in returns a structured,
actionable error.

## Client Integration

Documentation and copyable examples will cover:

- Codex desktop on macOS using project or user `config.toml` MCP settings;
- Codex CLI using the same MCP configuration surface;
- Claude Desktop on macOS using its MCP server JSON configuration; and
- Claude Code using its MCP registration command/configuration.

All examples will use stdio and the installed `terminal-mcp-server` command.
They will not depend on setting `PYTHONPATH` or on running from the repository
root. Examples will explain how the process finds `.env` and how a client can
override configuration explicitly.

Legacy Goose and Void examples may remain as secondary documentation if they
can be kept correct without changing the modern MCP schemas. Their historical
request-wrapping workaround will not dictate the primary interface.

## Error Handling

The backend boundary will distinguish:

- an unavailable application;
- denied macOS Automation or Accessibility permission;
- AppleScript timeout or execution failure;
- malformed AppleScript output;
- a stale or unknown session;
- an excluded self-session; and
- a write rejected by read-only policy.

MCP functions will translate these into stable structured results or supported
tool errors. Errors will include useful remediation without leaking terminal
contents or suggesting that a failed operation succeeded.

Logging will go to stderr so it cannot corrupt stdio MCP protocol traffic.
Normal operation will not log terminal input or screen contents at debug level
by default.

## Testing Strategy

Tests will be divided by boundary:

- Configuration tests verify safe defaults, `.env` loading, and explicit
  environment precedence.
- Backend unit tests verify AppleScript result parsing and command construction
  using controlled fixtures.
- Manager tests verify selection, caching, stale-session cleanup, explicit
  exclusions, and best-effort self-session detection.
- Policy tests verify every write tool is blocked by default and enabled by
  explicit local configuration.
- MCP contract tests connect through a FastMCP client, discover components,
  inspect schemas, and call representative tools using fake backends.
- Packaging tests build a wheel, install it in a clean environment, import the
  package, and launch the console entry point.
- A separately marked macOS smoke test may exercise a real terminal and will
  remain opt-in because it requires GUI state and permissions.

CI will test supported Python versions on macOS. Test failures will fail the
workflow. Formatting, linting, typing, package build/install, and MCP contract
checks will be mandatory rather than advisory. Security tooling will use
current maintained commands and fail only on defined actionable findings.

## Documentation and Release Scope

The README, quick start, contribution guide, install script, examples, and
changelog will agree on:

- supported Python versions;
- package installation and launch commands;
- stdio transport;
- current macOS System Settings terminology;
- read-only public defaults and local write opt-in;
- Codex and Claude setup;
- self-session limitations; and
- the standalone health check (with no nonexistent HTTP endpoint).

The release will be treated as a compatibility modernization. Unrelated new
terminal automation features are out of scope.

## Acceptance Criteria

The modernization is complete when:

1. A clean wheel installs and exposes a working `terminal-mcp-server` command.
2. Codex desktop can start the server over stdio, discover its tools, and use
   read and write operations when this checkout's `.env` enables writes.
3. Codex CLI, Claude Desktop, and Claude Code have equivalent verified setup
   instructions and pass the automated MCP contract suite.
4. The committed default blocks writes, while the ignored local `.env` enables
   them for this checkout.
5. `env.example` is visible and committed, while `.env` remains ignored and
   untracked.
6. Claude Code's hosting terminal is excluded when its controlling TTY can be
   identified, with documented override behavior.
7. Tool schemas contain no legacy client-specific request wrapper.
8. CI cannot pass when tests fail and verifies the distributable artifact.
9. Documentation contains no contradictory Python requirements or nonexistent
   HTTP health endpoint.

## External Compatibility References

- [Codex MCP customization documentation](https://developers.openai.com/codex/)
- [FastMCP release updates](https://github.com/PrefectHQ/fastmcp/blob/main/docs/updates.mdx)
- [MCP Python SDK documentation](https://py.sdk.modelcontextprotocol.io/)
