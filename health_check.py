#!/usr/bin/env python3
"""Side-effect-free installation diagnostics for Terminal MCP Server."""

from __future__ import annotations

import importlib.util
import shutil
import sys

from terminal_mcp.config import Settings


def _report(ok: bool, message: str) -> bool:
    print(f"{'OK' if ok else 'FAIL'}: {message}")
    return ok


def main() -> int:
    """Report prerequisites without querying, launching, or activating an app."""
    checks = [
        _report(
            sys.version_info >= (3, 10),
            f"Python {sys.version.split()[0]} (3.10+ required)",
        ),
        _report(
            sys.platform == "darwin", f"platform is {sys.platform} (macOS required)"
        ),
    ]
    for dependency in ("fastmcp", "pydantic", "dotenv", "terminal_mcp"):
        checks.append(
            _report(
                importlib.util.find_spec(dependency) is not None, f"import {dependency}"
            )
        )
    checks.append(
        _report(shutil.which("osascript") is not None, "osascript is available")
    )
    settings = Settings.load()
    mode = "read-only" if settings.readonly else "writable"
    print(f"INFO: effective mode is {mode}")
    print("INFO: Accessibility/Automation permission is checked only when a tool runs")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
