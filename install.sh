#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

echo "Installing Terminal MCP Server..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: Python 3.10 or newer is required."
    exit 1
fi

python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "Error: Python 3.10 or newer is required. Found: $python_version"
    exit 1
fi

if [ "$(uname -s)" != "Darwin" ]; then
    echo "Error: Terminal MCP Server requires macOS."
    exit 1
fi

echo "Python $python_version detected."
if command -v uv >/dev/null 2>&1; then
    uv venv --python python3 .venv
    uv pip install --python .venv/bin/python .
else
    python3 -m venv .venv
    .venv/bin/python -m pip install .
fi

if [ ! -f .env ]; then
    cp env.example .env
    echo "Created .env from env.example."
    echo "Terminal writes are disabled by default until you edit .env."
else
    echo "Preserved existing .env."
    echo "Inspect MCP_TERMINAL_READONLY in .env to confirm the current write policy."
fi

echo "Installation complete."
echo "Run: .venv/bin/python -m terminal_mcp"
echo "Health check: .venv/bin/python health_check.py"
