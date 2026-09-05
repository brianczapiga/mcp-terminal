# Client setup

Run `make setup` and `cp env.example .env` first. In every example, replace `/absolute/path/to/mcp-terminal` with the repository's absolute path. Absolute paths matter because desktop apps do not inherit your shell working directory or environment.

All integrations below launch the same installed `terminal-mcp-server` command as a local stdio subprocess. `MCP_TERMINAL_ENV_FILE` tells it exactly which `.env` to load.

## Codex desktop on macOS

Codex desktop and the Codex CLI share `~/.codex/config.toml`. Merge [the example](../examples/codex-config.toml) into that file, then fully quit and reopen Codex. Start a new conversation and ask Codex to list terminal sessions.

The example uses the documented `command`, `env`, `startup_timeout_sec`, and `tool_timeout_sec` stdio settings. The file location and schema were verified against the [official Codex MCP guide](https://developers.openai.com/codex/mcp/) and [configuration reference](https://developers.openai.com/codex/config-reference/).

## Codex CLI

Either use the same TOML configuration or add it from the command line:

```bash
codex mcp add terminal \
  --env MCP_TERMINAL_ENV_FILE=/absolute/path/to/mcp-terminal/.env \
  -- /absolute/path/to/mcp-terminal/.venv/bin/terminal-mcp-server
codex mcp get terminal
```

Start a new `codex` session after adding or changing the server. This syntax was verified with the locally installed `codex mcp add --help`; the local help does not expose timeout flags, so set timeouts in TOML.

## Claude Desktop on macOS

Merge [the JSON example](../examples/claude-desktop-config.json) into:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

Fully quit Claude Desktop and reopen it. The `mcpServers` JSON shape and restart behavior are documented by the [official MCP Python SDK host guide](https://py.sdk.modelcontextprotocol.io/get-started/real-host/). Anthropic's current Desktop help emphasizes Extensions/DXT rather than hand-edited local JSON, so this legacy developer configuration is secondary and was not exercised against a signed-in Desktop app.

## Claude Code

Add the server for your user account:

```bash
claude mcp add --scope user --transport stdio \
  terminal --env MCP_TERMINAL_ENV_FILE=/absolute/path/to/mcp-terminal/.env \
  -- /absolute/path/to/mcp-terminal/.venv/bin/terminal-mcp-server
claude mcp get terminal
```

Start a new Claude Code session after configuration changes. The option ordering, `--` separator, scopes, and verification command were checked against both local `claude mcp add --help` and Anthropic's [official Claude Code MCP reference](https://code.claude.com/docs/en/mcp).

When Claude Code itself runs inside Terminal.app or iTerm2, add its TTY (for example `/dev/ttys004`) to `MCP_TERMINAL_EXCLUDED_TTYS` in `.env`. This is a best-effort exclusion: self-session detection can be ambiguous across process trees and terminal tabs.

## Safety notes

The checked-in `env.example` enables read-only mode. Set `MCP_TERMINAL_READONLY=0` only when you deliberately want the three write tools. Keep `MCP_TERMINAL_ALLOW_SELF_TARGET=0`: overriding it can make the server type into, interrupt, or otherwise destabilize the client session hosting it.

On first use, macOS may request Automation or Accessibility permission. Configure these under **System Settings → Privacy & Security**. The local health check deliberately does not trigger an Apple event and therefore cannot certify permissions.
