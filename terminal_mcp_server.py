#!/usr/bin/env python3
"""Compatibility launcher for the packaged Terminal MCP server."""

from terminal_mcp.manager import TerminalManager
from terminal_mcp.models import SessionInfo
from terminal_mcp.server import create_server, main

__all__ = ["SessionInfo", "TerminalManager", "create_server", "main"]

if __name__ == "__main__":
    main()
