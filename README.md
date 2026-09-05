# Terminal MCP Server

A local [Model Context Protocol](https://modelcontextprotocol.io/) server that lets an MCP client inspect and, when explicitly enabled, control macOS Terminal.app or iTerm2 through AppleScript. It communicates over stdio and opens no network port.

## Requirements and installation

- macOS with Terminal.app or iTerm2
- Python 3.10 or newer

```bash
git clone https://github.com/brianczapiga/mcp-terminal.git
cd mcp-terminal
make setup
cp env.example .env
make health
```

`make health` is a standalone local diagnostic. It checks imports and prerequisites without opening or querying terminal apps; it is not an HTTP health endpoint.

Configure a client with the absolute path to `.venv/bin/terminal-mcp-server` and to `.env`. See [Codex and Claude setup](docs/CLIENTS.md). Secondary examples for [Goose](examples/goose_config.json) and [Void](examples/void_config.yaml) are included but are not verified in CI.

## Tools

The server exposes eight tools:

- `list_sessions`, `set_active_session`
- `get_screen`, `get_all_terminal_info`, `scroll_back`
- `send_input`, `send_keypress`, `paste_text`

`send_keypress` accepts a single character or `return`, `tab`, `escape`, `delete`,
`up`, `down`, `left`, or `right`, with optional `command`, `control`, `option`, and
`shift` modifiers. For example, `{"key": "up"}` recalls shell history without
pressing Return.

It also provides a per-session resource and workflow, summary, command-suggestion, and troubleshooting prompts.

The MCP handshake and tool discovery do not query macOS. Terminal and self-session
detection run when a tool first needs sessions. If terminal detection fails, the
tool returns an error and the next call tries detection again on the same MCP
connection. Successful backend selection is cached for that server process;
writes are never automatically retried after an error or timeout.

## Safety and permissions

The public default is read-only (`MCP_TERMINAL_READONLY=1`). To opt into terminal writes, set `MCP_TERMINAL_READONLY=0` in `.env`; only do this for clients and projects you trust.

On current macOS, grant the MCP client access under **System Settings → Privacy & Security → Automation** when prompted. Depending on how the client launches the server, macOS may also request **Accessibility** access. `make health` cannot prove these permissions without triggering automation, so permission failures appear on the first real tool call.

Permission errors returned to the agent include the relevant Settings path and
recovery steps. Automation controls access to other apps; Accessibility permits
GUI input such as keystrokes. A successful screen read does not establish keyboard
access. Enable the app macOS identifies as requesting access, which may be the
MCP client or its terminal host. See Apple's guidance for
[Automation](https://support.apple.com/guide/mac-help/mchl108e1718/mac) and
[Accessibility](https://support.apple.com/guide/mac-help/mh43185/mac).
Read-only policy errors explain which environment setting to change and when to
restart the server. Generic errors and timeouts are not labeled permission denials.

Self-session detection reduces the chance of targeting the terminal session that hosts the MCP client, but detection is best effort. Claude Code hosted from a terminal may need its TTY added to `MCP_TERMINAL_EXCLUDED_TTYS`. `MCP_TERMINAL_ALLOW_SELF_TARGET=1` overrides the guard and can create feedback loops or disrupt the client itself.

## Development

```bash
make setup
make check
```

With an existing Terminal.app tab and Automation permission, run the read-only
screen regression check with
`MCP_TERMINAL_SMOKE=1 .venv/bin/pytest -m smoke -q`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contributor commands and [QUICKSTART.md](QUICKSTART.md) for the shortest setup path.

## License

MIT. See [LICENSE](LICENSE).
