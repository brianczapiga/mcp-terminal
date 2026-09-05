"""Domain errors raised by terminal MCP operations."""


class TerminalMcpError(Exception):
    """Base class for expected terminal MCP failures."""


class ApplicationUnavailable(TerminalMcpError):
    """The terminal application or required system executable is unavailable."""


class AutomationDenied(TerminalMcpError):
    """macOS denied the requested automation operation."""


class AccessibilityDenied(TerminalMcpError):
    """macOS denied assistive access needed for GUI input."""


class ScriptTimedOut(TerminalMcpError):
    """An automation script exceeded its execution deadline."""


class ScriptFailed(TerminalMcpError):
    """An automation script failed for a non-permission reason."""


class MalformedResponse(TerminalMcpError):
    """An automation response could not be parsed."""


class UnknownSession(TerminalMcpError):
    """A requested terminal session does not exist."""


class ExcludedSession(TerminalMcpError):
    """A requested terminal session is excluded by policy."""


class WriteDisabled(TerminalMcpError):
    """A write was attempted while terminal writes are disabled."""
