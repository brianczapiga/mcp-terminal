"""Non-launching terminal backend detection."""

from terminal_mcp.backends.base import AppleScriptRunner
from terminal_mcp.backends.iterm2 import ITerm2Backend
from terminal_mcp.backends.macos_terminal import MacOSTerminalBackend
from terminal_mcp.errors import ApplicationUnavailable, AutomationDenied, ScriptFailed


def _is_running(runner: AppleScriptRunner, process_name: str) -> bool:
    script = (
        'tell application "System Events" to return '
        f'(exists process "{process_name}") as text'
    )
    result = runner.run(script).strip().casefold()
    if result not in {"true", "false"}:
        raise ApplicationUnavailable("Application status could not be determined")
    return result == "true"


def _probe(runner: AppleScriptRunner, application: str) -> bool:
    try:
        result = runner.run(
            'tell application "System Events"\n'
            f'if not (exists process "{application}") then return "not-running"\n'
            "end tell\n"
            f'tell application "{application}" to return name'
        )
    except AutomationDenied:
        raise
    except (ApplicationUnavailable, ScriptFailed):
        return False
    return result != "not-running"


def detect_backend(runner: AppleScriptRunner):  # type: ignore[no-untyped-def]
    """Choose the preferred running, script-accessible terminal application."""
    if _is_running(runner, "iTerm2") and _probe(runner, "iTerm2"):
        return ITerm2Backend(runner)
    if _is_running(runner, "Terminal") and _probe(runner, "Terminal"):
        return MacOSTerminalBackend(runner)
    raise ApplicationUnavailable("No supported terminal application is accessible")
