# Quick start

Terminal MCP Server requires macOS, Terminal.app or iTerm2, and Python 3.10+.

```bash
git clone https://github.com/brianczapiga/mcp-terminal.git
cd mcp-terminal
make setup
cp env.example .env
make health
```

Then follow [Codex or Claude client setup](docs/CLIENTS.md), replacing every example `/absolute/path/to/mcp-terminal` with this repository's absolute path. The client launches `.venv/bin/terminal-mcp-server` as a stdio subprocess; do not start a web server.

The default `.env` is read-only. After confirming reads work, opt into `send_input`, `send_keypress`, and `paste_text` by setting `MCP_TERMINAL_READONLY=0`. Fully restart desktop clients or start a new CLI session after configuration changes.

If a tool reports automation denial, open **System Settings → Privacy & Security → Automation** and allow the client to control Terminal.app or iTerm2. Accessibility may also be requested. For a terminal-hosted client, exclude its TTY with `MCP_TERMINAL_EXCLUDED_TTYS`; self-session detection is best effort.
