"""Terminal application backend interfaces."""

from terminal_mcp.backends.base import AppleScriptRunner, TerminalBackend
from terminal_mcp.backends.detect import detect_backend
from terminal_mcp.backends.iterm2 import ITerm2Backend
from terminal_mcp.backends.macos_terminal import MacOSTerminalBackend

__all__ = [
    "AppleScriptRunner",
    "ITerm2Backend",
    "MacOSTerminalBackend",
    "TerminalBackend",
    "detect_backend",
]
