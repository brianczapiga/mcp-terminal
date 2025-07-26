#!/usr/bin/env python3
"""
MCP Server for macOS Terminal Integration
Allows AI tools to collaborate with Terminal sessions via AppleScript.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field


# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Security: Readonly mode check
def is_readonly_mode() -> bool:
    """Check if the server is running in readonly mode."""
    return os.getenv("MCP_TERMINAL_READONLY", "0").lower() in ("1", "true", "yes", "on")


@dataclass
class SessionInfo:
    """Information about a Terminal session (window/tab)."""

    window_id: str
    tab_id: str
    name: str
    tty_device: Optional[str]
    last_activity: float
    is_active: bool


@dataclass
class ScreenContent:
    """Screen content for a session."""

    session_id: str
    content: str
    timestamp: float
    line_count: int


class TerminalManager:
    """Manages Terminal sessions via AppleScript."""

    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}
        self.active_session_id: Optional[str] = None
        self.output_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
        self.last_scan_time = 0
        self.scan_interval = 2.0  # seconds
        self.terminal_app = self._detect_terminal_app()

    def _detect_terminal_app(self) -> str:
        """Detect which terminal application is available."""
        # Check for iTerm2 first
        iterm_check = self._run_applescript(
            """
        tell application "System Events"
            try
                get name of every process whose name contains "iTerm"
                return "iTerm2"
            on error
                return "Terminal"
            end try
        end tell
        """
        )

        # Test if iTerm2 is actually accessible
        if "iTerm2" in iterm_check:
            # Try to actually connect to iTerm2
            test_iterm = self._run_applescript(
                """
            tell application "iTerm2"
                try
                    get name of windows
                    return "iTerm2"
                on error
                    return "Terminal"
                end try
            end tell
            """
            )

            if "iTerm2" in test_iterm:
                logger.info("Detected iTerm2")
                return "iTerm2"

        logger.info("Using Apple Terminal")
        return "Terminal"

    def _run_applescript(self, script: str) -> str:
        """Execute AppleScript and return the result."""
        try:
            logger.debug(f"Executing AppleScript: {script[:100]}...")
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.error(f"AppleScript error: {result.stderr}")
                return ""
            logger.debug(f"AppleScript result: {result.stdout.strip()}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error("AppleScript execution timed out")
            return ""
        except Exception as e:
            logger.error(f"AppleScript execution failed: {e}")
            return ""

    def scan_sessions(self) -> List[SessionInfo]:
        """Scan for all Terminal sessions and update internal state."""
        current_time = time.time()
        if current_time - self.last_scan_time < self.scan_interval:
            logger.info(
                f"Using cached sessions (scanned {current_time - self.last_scan_time:.1f}s ago)"
            )
            return list(self.sessions.values())

        logger.info(f"Scanning {self.terminal_app} sessions...")

        if self.terminal_app == "iTerm2":
            result = self._scan_iterm2_sessions()
        else:
            result = self._scan_terminal_sessions()

        logger.info(f"Scan completed, found {len(result)} sessions")
        return result

    def _scan_terminal_sessions(self) -> List[SessionInfo]:
        """Scan Apple Terminal sessions with improved parsing."""
        script = """
        tell application "Terminal"
            set sessionList to {}
            set windowCount to count of windows
            repeat with i from 1 to windowCount
                set w to item i of windows
                set windowId to (id of w) as string
                set tabCount to count of tabs of w
                repeat with j from 1 to tabCount
                    set t to item j of tabs of w
                    set tabId to j as string
                    set tabName to custom title of t
                    if tabName is "" then
                        set tabName to name of t
                    end if
                    if tabName is "" then
                        set tabName to "Terminal Session"
                    end if
                    set tabTty to tty of t
                    set tabBusy to busy of t
                    
                    set sessionInfo to {windowId, tabId, tabName, tabTty, tabBusy}
                    copy sessionInfo to end of sessionList
                end repeat
            end repeat
            return sessionList
        end tell
        """

        result = self._run_applescript(script)
        sessions = []

        try:
            # Parse the AppleScript result
            # The result might be a single line with all session data
            if "," in result and not "\n" in result:
                # Single line format: "75081, 1, Terminal, /dev/ttys000, false, 74477, 1, Terminal, /dev/ttys001, false"
                parts = result.split(", ")
                i = 0
                while i < len(parts) - 4:  # Need at least 5 parts per session
                    window_id = parts[i].strip()
                    tab_id = parts[i + 1].strip()
                    name = parts[i + 2].strip().strip('"')
                    tty = parts[i + 3].strip().strip('"')
                    busy = parts[i + 4].strip() == "true"

                    session_id = f"{window_id}_{tab_id}"
                    session_info = SessionInfo(
                        window_id=window_id,
                        tab_id=tab_id,
                        name=name,
                        tty_device=tty if tty != "missing value" else None,
                        last_activity=time.time(),
                        is_active=busy,
                    )
                    self.sessions[session_id] = session_info
                    sessions.append(session_info)
                    i += 5
            else:
                # Multi-line format (original parsing)
                lines = result.split("\n")
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    if line and not line.startswith('"') and not line.startswith("{"):
                        # This should be a session entry
                        parts = line.split(", ")
                        if len(parts) >= 5:
                            window_id = parts[0].strip()
                            tab_id = parts[1].strip()
                            name = parts[2].strip().strip('"')
                            tty = parts[3].strip().strip('"')
                            busy = parts[4].strip() == "true"

                            session_id = f"{window_id}_{tab_id}"
                            session_info = SessionInfo(
                                window_id=window_id,
                                tab_id=tab_id,
                                name=name,
                                tty_device=tty if tty != "missing value" else None,
                                last_activity=time.time(),
                                is_active=busy,
                            )
                            self.sessions[session_id] = session_info
                            sessions.append(session_info)
                    i += 1

        except Exception as e:
            logger.error(f"Failed to parse Terminal sessions: {e}")
            # Fallback to simpler parsing
            return self._scan_terminal_sessions_fallback()

        # If no sessions were found, try fallback
        if not sessions:
            logger.info("No sessions found in main parsing, trying fallback")
            return self._scan_terminal_sessions_fallback()

        self.last_scan_time = time.time()
        return sessions

    def _scan_terminal_sessions_fallback(self) -> List[SessionInfo]:
        """Fallback method for parsing Terminal sessions."""
        script = """
        tell application "Terminal"
            set sessionCount to 0
            repeat with w in windows
                repeat with t in tabs of w
                    set sessionCount to sessionCount + 1
                end repeat
            end repeat
            return sessionCount
        end tell
        """

        count_result = self._run_applescript(script)
        try:
            count = int(count_result)
            if count > 0:
                # Create a basic session info
                session_info = SessionInfo(
                    window_id="1",
                    tab_id="1",
                    name="Terminal Session",
                    tty_device=None,
                    last_activity=time.time(),
                    is_active=True,
                )
                session_id = "1_1"
                self.sessions[session_id] = session_info
                return [session_info]
        except ValueError:
            pass

        # If that fails, try a simpler approach
        simple_script = """
        tell application "Terminal"
            try
                get name of windows
                return "1"
            on error
                return "0"
            end try
        end tell
        """

        simple_result = self._run_applescript(simple_script)
        if "1" in simple_result:
            # Create a basic session info
            session_info = SessionInfo(
                window_id="1",
                tab_id="1",
                name="Terminal Session",
                tty_device=None,
                last_activity=time.time(),
                is_active=True,
            )
            session_id = "1_1"
            self.sessions[session_id] = session_info
            return [session_info]

        return []

    def _scan_iterm2_sessions(self) -> List[SessionInfo]:
        """Scan iTerm2 sessions."""
        script = """
        tell application "iTerm2"
            set sessionList to {}
            repeat with w in windows
                set windowId to id of w as string
                repeat with t in tabs of w
                    set tabId to id of t as string
                    set tabName to name of t
                    
                    set sessionInfo to {windowId, tabId, tabName}
                    copy sessionInfo to end of sessionList
                end repeat
            end repeat
            return sessionList
        end tell
        """

        result = self._run_applescript(script)
        sessions = []

        try:
            lines = result.split("\n")
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line and not line.startswith('"'):
                    parts = line.split(", ")
                    if len(parts) >= 3:
                        window_id = parts[0].strip()
                        tab_id = parts[1].strip()
                        name = parts[2].strip().strip('"')

                        session_id = f"{window_id}_{tab_id}"
                        session_info = SessionInfo(
                            window_id=window_id,
                            tab_id=tab_id,
                            name=name,
                            tty_device=None,  # iTerm2 doesn't expose TTY easily
                            last_activity=time.time(),
                            is_active=True,
                        )
                        self.sessions[session_id] = session_info
                        sessions.append(session_info)
                i += 1

        except Exception as e:
            logger.error(f"Failed to parse iTerm2 sessions: {e}")

        return sessions

    def get_session_content(self, session_id: str, lines: int = 100) -> str:
        """Get the content of a specific session."""
        if session_id not in self.sessions:
            return f"Session {session_id} not found"

        session = self.sessions[session_id]

        if self.terminal_app == "Terminal":
            # Find the window index for this session
            window_index = None
            script_find = (
                '''
            tell application "Terminal"
                set windowCount to count of windows
                repeat with i from 1 to windowCount
                    set w to item i of windows
                    if (id of w as string) is "'''
                + session.window_id
                + """" then
                        return i as string
                    end if
                end repeat
            end tell
            """
            )
            window_index_result = self._run_applescript(script_find)

            if window_index_result and window_index_result.isdigit():
                window_index = int(window_index_result)
                # Use direct AppleScript to get content from specific window
                script = f'tell application "Terminal" to get contents of item 1 of tabs of item {window_index} of windows'
            else:
                # Fallback to first window
                script = 'tell application "Terminal" to get contents of item 1 of tabs of item 1 of windows'
        else:  # iTerm2
            script = f"""
            tell application "iTerm2"
                repeat with w in windows
                    if (id of w as string) is "{session.window_id}" then
                        repeat with t in tabs of w
                            if (id of t as string) is "{session.tab_id}" then
                                return contents of t
                            end if
                        end repeat
                    end if
                end repeat
            end tell
            """

        content = self._run_applescript(script)

        # Update buffer
        if content and content != "Unable to retrieve terminal content":
            self.output_buffers[session_id].append(
                {
                    "content": content,
                    "timestamp": time.time(),
                    "line_count": len(content.split("\n")),
                }
            )

        # Return last N lines
        lines_list = content.split("\n")
        return "\n".join(lines_list[-lines:]) if lines_list else ""

    def send_input(self, session_id: str, text: str, execute: bool = True) -> bool:
        """Send input to a specific session."""
        if session_id not in self.sessions:
            logger.error(f"Session {session_id} not found")
            return False

        session = self.sessions[session_id]

        if self.terminal_app == "Terminal":
            if execute:
                script = f"""
                tell application "Terminal"
                    set windowCount to count of windows
                    repeat with i from 1 to windowCount
                        set w to item i of windows
                        if (id of w as string) is "{session.window_id}" then
                            set tabCount to count of tabs of w
                            repeat with j from 1 to tabCount
                                set t to item j of tabs of w
                                if j as string is "{session.tab_id}" then
                                    do script "{text}" in t
                                    return true
                                end if
                            end repeat
                        end if
                    end repeat
                end tell
                """
            else:
                # Just type the text without executing
                script = f"""
                tell application "System Events"
                    tell process "Terminal"
                        set frontmost to true
                        keystroke "{text}"
                    end tell
                end tell
                """
        else:  # iTerm2
            if execute:
                script = f"""
                tell application "iTerm2"
                    repeat with w in windows
                        if (id of w as string) is "{session.window_id}" then
                            repeat with t in tabs of w
                                if (id of t as string) is "{session.tab_id}" then
                                    write text "{text}" in t
                                    return true
                                end if
                            end repeat
                        end if
                    end repeat
                end tell
                """
            else:
                script = f"""
                tell application "System Events"
                    tell process "iTerm2"
                        set frontmost to true
                        keystroke "{text}"
                    end tell
                end tell
                """

        result = self._run_applescript(script)
        return "true" in result.lower() or result == ""

    def send_keypress(
        self, session_id: str, key: str, modifiers: Optional[List[str]] = None
    ) -> bool:
        """Send a specific keypress to a session."""
        if session_id not in self.sessions:
            logger.error(f"Session {session_id} not found")
            return False

        session = self.sessions[session_id]

        # Map special keys to AppleScript key codes
        key_mapping = {
            "tab": "key code 48",
            "escape": "key code 53",
            "return": "key code 36",
            "enter": "key code 76",
            "space": "key code 49",
            "delete": "key code 51",
            "backspace": "key code 51",
            "up": "key code 126",
            "down": "key code 125",
            "left": "key code 123",
            "right": "key code 124",
            "home": "key code 115",
            "end": "key code 119",
            "pageup": "key code 116",
            "pagedown": "key code 121",
        }

        # Build the keystroke command
        if key.lower() in key_mapping:
            keystroke_cmd = key_mapping[key.lower()]
        else:
            # For regular characters, use keystroke
            keystroke_cmd = f'keystroke "{key}"'

        # Add modifiers if specified
        if modifiers:
            modifier_list = []
            for mod in modifiers:
                if mod.lower() in ["command", "cmd"]:
                    modifier_list.append("command down")
                elif mod.lower() in ["shift"]:
                    modifier_list.append("shift down")
                elif mod.lower() in ["option", "alt"]:
                    modifier_list.append("option down")
                elif mod.lower() in ["control", "ctrl"]:
                    modifier_list.append("control down")

            if modifier_list:
                keystroke_cmd += f' using {{{", ".join(modifier_list)}}}'

        if self.terminal_app == "Terminal":
            script = f"""
            tell application "System Events"
                tell process "Terminal"
                    set frontmost to true
                    {keystroke_cmd}
                end tell
            end tell
            """
        else:  # iTerm2
            script = f"""
            tell application "System Events"
                tell process "iTerm2"
                    set frontmost to true
                    {keystroke_cmd}
                end tell
            end tell
            """

        result = self._run_applescript(script)
        return "true" in result.lower() or result == ""

    def paste_text(self, session_id: str, text: str) -> bool:
        """Paste text into a session using Cmd+V."""
        if session_id not in self.sessions:
            logger.error(f"Session {session_id} not found")
            return False

        session = self.sessions[session_id]

        # First, set the text to clipboard
        clipboard_script = f"""
        set the clipboard to "{text}"
        """
        self._run_applescript(clipboard_script)

        # Then paste it using Cmd+V
        if self.terminal_app == "Terminal":
            script = f"""
            tell application "System Events"
                tell process "Terminal"
                    set frontmost to true
                    keystroke "v" using command down
                end tell
            end tell
            """
        else:  # iTerm2
            script = f"""
            tell application "System Events"
                tell process "iTerm2"
                    set frontmost to true
                    keystroke "v" using command down
                end tell
            end tell
            """

        result = self._run_applescript(script)
        return "true" in result.lower() or result == ""

    def get_most_recent_tty(self) -> Optional[str]:
        """Find the TTY device with the most recent write activity."""
        try:
            tty_devices = Path("/dev").glob("ttys*")
            most_recent = None
            most_recent_time = 0

            for tty_path in tty_devices:
                try:
                    stat = tty_path.stat()
                    if stat.st_mtime > most_recent_time:
                        most_recent_time = stat.st_mtime
                        most_recent = str(tty_path)
                except (OSError, PermissionError):
                    continue

            return most_recent
        except Exception as e:
            logger.error(f"Error finding most recent TTY: {e}")
            return None

    def set_active_session(self, session_id: str) -> bool:
        """Set the active session for operations."""
        if session_id in self.sessions:
            self.active_session_id = session_id
            logger.info(f"Active session set to: {session_id}")
            return True
        else:
            logger.error(f"Session {session_id} not found")
            return False

    def get_active_session_content(self, lines: int = 100) -> str:
        """Get content from the active session."""
        if not self.active_session_id:
            return "No active session set"
        return self.get_session_content(self.active_session_id, lines)

    def scroll_back(self, session_id: str, pages: int = 1) -> str:
        """Get older content from the buffer."""
        if session_id not in self.output_buffers:
            return "No buffer available for this session"

        buffer = self.output_buffers[session_id]
        if not buffer:
            return "Buffer is empty"

        # Calculate how many entries to go back (roughly 50 lines per page)
        entries_to_go_back = min(pages * 5, len(buffer))
        if entries_to_go_back == 0:
            return "No older content available"

        # Get older content
        older_entries = list(buffer)[-entries_to_go_back:]
        content = "\n".join([entry["content"] for entry in older_entries])

        return content


# MCP Server Models
class ListSessionsResponse(BaseModel):
    sessions: List[str]


class SetActiveSessionRequest(BaseModel):
    session_id: str = Field(..., description="The session ID to set as active")


class GetScreenRequest(BaseModel):
    lines: int = Field(default=100, description="Number of lines to retrieve")
    mode: str = Field(default="focus", description="Mode: focus, recent-output, manual")


class SendInputRequest(BaseModel):
    text: str = Field(..., description="Text to send to the terminal")
    execute: bool = Field(
        default=True, description="Whether to execute the command (press Enter)"
    )
    session_id: Optional[str] = Field(
        None, description="Session ID to send to (uses active if not specified)"
    )


class SendKeypressRequest(BaseModel):
    key: str = Field(
        ...,
        description="Key to press (e.g., 'return', 'tab', 'escape', 'up', 'down', 'left', 'right')",
    )
    modifiers: Optional[List[str]] = Field(
        default=None, description="Modifier keys (e.g., ['command', 'shift'])"
    )
    session_id: Optional[str] = Field(
        None, description="Session ID to send to (uses active if not specified)"
    )


class PasteTextRequest(BaseModel):
    text: str = Field(..., description="Text to paste into the terminal")
    session_id: Optional[str] = Field(
        None, description="Session ID to send to (uses active if not specified)"
    )


class ScrollBackRequest(BaseModel):
    pages: int = Field(default=1, description="Number of pages to scroll back")
    session_id: Optional[str] = Field(
        None, description="Session ID to scroll back (uses active if not specified)"
    )


# Initialize the terminal manager
terminal_manager = TerminalManager()


# MCP Server
server = FastMCP("terminal-mcp-server")
logger.info("FastMCP server created")


# Add resources for terminal sessions
@server.resource("terminal://session/{session_id}")
async def get_terminal_session(session_id: str) -> str:
    """Get the content of a terminal session."""
    try:
        if session_id not in terminal_manager.sessions:
            return f"Session {session_id} not found"

        content = terminal_manager.get_session_content(session_id, lines=100)
        return content
    except Exception as e:
        logger.error(f"Error reading session {session_id}: {e}")
        return f"Error reading session: {str(e)}"


# Add prompts for terminal assistance
@server.prompt("terminal_workflow_guide")
async def terminal_workflow_guide() -> str:
    """Complete guide for working with terminal sessions via MCP tools.

    This guide explains how to use the terminal MCP tools together to examine and interact with terminal sessions.

    RECOMMENDED WORKFLOW (Single Call):

    1. GET ALL INFORMATION AT ONCE:
       - Call get_all_terminal_info() to get everything in one response
       - This returns session IDs, content, and metadata for all sessions
       - This is the preferred approach to avoid sequential tool call issues

    ALTERNATIVE WORKFLOW (Multiple Calls):

    1. DISCOVER SESSIONS:
       - Call list_sessions() to get all available terminal session IDs
       - This returns a list like ["75294_1", "76536_1"]

    2. EXAMINE INDIVIDUAL SESSIONS:
       For each session you want to examine:
       a) set_active_session(session_id) - switch to that session
       b) get_screen() - get the current content from that session
       c) Repeat for each session



    RECOMMENDED EXAMPLE:
    - get_all_terminal_info() → returns everything about all sessions in one call

    ALTERNATIVE EXAMPLE:
    - list_sessions() → ["75294_1", "76536_1"]
    - set_active_session("75294_1") → switch to first session
    - get_screen() → get content from first session
    - set_active_session("76536_1") → switch to second session
    - get_screen() → get content from second session

    IMPORTANT NOTES:
    - Use get_all_terminal_info() for the most reliable single-call approach
    - Session IDs are in format "window_id_tab_id" (e.g., "75294_1")
    - The comprehensive tool avoids sequential tool call timing issues
    """


@server.prompt("terminal_session_summary")
async def terminal_session_summary(
    session_id: str, include_history: bool = False
) -> str:
    """Generate a summary of the current terminal session.

    This prompt helps you understand how to work with terminal sessions.

    To get a summary of a terminal session:
    1. First call list_sessions() to see available sessions
    2. Use set_active_session(session_id) to select the session
    3. Call get_screen() to get the current content
    4. Then use this prompt to generate a summary
    """
    try:
        if session_id not in terminal_manager.sessions:
            return f"Session {session_id} not found"

        session = terminal_manager.sessions[session_id]
        content = terminal_manager.get_session_content(session_id, lines=50)

        summary = f"Session: {session.name}\n"
        summary += f"Window ID: {session.window_id}, Tab ID: {session.tab_id}\n"
        summary += f"TTY Device: {session.tty_device or 'Unknown'}\n"
        summary += f"Active: {session.is_active}\n\n"
        summary += f"Recent Content:\n{content}"

        if include_history:
            history = terminal_manager.scroll_back(session_id, pages=2)
            summary += f"\n\nCommand History:\n{history}"

        return summary
    except Exception as e:
        logger.error(f"Error generating session summary: {e}")
        return f"Error generating summary: {str(e)}"


@server.prompt("terminal_command_suggestion")
async def terminal_command_suggestion(session_id: str, context: str = "") -> str:
    """Suggest the next command based on current terminal state."""
    try:
        if session_id not in terminal_manager.sessions:
            return f"Session {session_id} not found"

        content = terminal_manager.get_session_content(session_id, lines=20)

        suggestion = f"Based on the current terminal state:\n\n"
        suggestion += f"Recent output:\n{content}\n\n"

        if context:
            suggestion += f"Context: {context}\n\n"

        suggestion += "Suggested next commands:\n"
        suggestion += "1. Check current directory: `pwd`\n"
        suggestion += "2. List files: `ls -la`\n"
        suggestion += "3. Check process status: `ps aux`\n"
        suggestion += "4. Check disk usage: `df -h`\n"

        return suggestion
    except Exception as e:
        logger.error(f"Error generating command suggestion: {e}")
        return f"Error generating suggestion: {str(e)}"


@server.prompt("terminal_troubleshooting")
async def terminal_troubleshooting(session_id: str) -> str:
    """Analyze terminal session for potential issues."""
    try:
        if session_id not in terminal_manager.sessions:
            return f"Session {session_id} not found"

        session = terminal_manager.sessions[session_id]
        content = terminal_manager.get_session_content(session_id, lines=30)

        analysis = f"Terminal Session Analysis:\n\n"
        analysis += f"Session: {session.name}\n"
        analysis += f"TTY Device: {session.tty_device or 'Unknown'}\n"
        analysis += f"Active: {session.is_active}\n\n"

        # Basic troubleshooting checks
        if "error" in content.lower():
            analysis += "⚠️  Errors detected in recent output\n"
        if "permission denied" in content.lower():
            analysis += "⚠️  Permission issues detected\n"
        if "command not found" in content.lower():
            analysis += "⚠️  Missing commands detected\n"

        analysis += f"\nRecent output:\n{content}\n\n"
        analysis += "Troubleshooting suggestions:\n"
        analysis += "1. Check if the session is responsive\n"
        analysis += "2. Verify file permissions\n"
        analysis += "3. Check if required commands are installed\n"
        analysis += "4. Restart the terminal session if needed\n"

        return analysis
    except Exception as e:
        logger.error(f"Error generating troubleshooting analysis: {e}")
        return f"Error generating analysis: {str(e)}"


@server.tool()
async def list_sessions() -> ListSessionsResponse:
    """List all Terminal sessions (windows/tabs) with their IDs.

    This tool returns a simple list of session IDs. For comprehensive information about all sessions
    including their content, use get_all_terminal_info() instead.

    Workflow:
    1. Call list_sessions() to get available session IDs
    2. Use set_active_session(session_id) to select a specific session
    3. Use get_screen() to retrieve content from the active session
    4. Repeat steps 2-3 for each session you want to examine

    RECOMMENDED: Use get_all_terminal_info() instead for a single call that returns everything.

    Example workflow:
    - list_sessions() → returns ["75294_1", "76536_1"]
    - set_active_session("75294_1") → switches to first session
    - get_screen() → gets content from first session
    - set_active_session("76536_1") → switches to second session
    - get_screen() → gets content from second session
    """
    try:
        logger.info("list_sessions tool called")
        sessions = terminal_manager.scan_sessions()
        logger.info(f"scan_sessions returned {len(sessions)} sessions")

        session_ids = []

        for session in sessions:
            session_id = f"{session.window_id}_{session.tab_id}"
            session_ids.append(session_id)

        logger.info(f"Session IDs: {session_ids}")

        response = ListSessionsResponse(sessions=session_ids)
        logger.info(f"Created response object: {response}")
        logger.info(f"Response type: {type(response)}")
        logger.info(f"Response sessions: {response.sessions}")

        return response
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        empty_response = ListSessionsResponse(sessions=[])
        logger.info(f"Returning empty response: {empty_response}")
        return empty_response


@server.tool()
async def set_active_session(
    request: SetActiveSessionRequest,
) -> Dict[str, Union[bool, str]]:
    """Set the active session for terminal operations.

    This tool switches the focus to a specific terminal session. You must call this before
    using get_screen() to retrieve content from a specific session.

    Usage:
    1. First call list_sessions() to get available session IDs
    2. Call set_active_session(session_id) with one of the returned session IDs
    3. Then call get_screen() to get content from that session

    The session_id should be in the format "window_id_tab_id" (e.g., "75294_1").
    """
    try:
        success = terminal_manager.set_active_session(request.session_id)
        return {
            "success": success,
            "message": f"Active session set to {request.session_id}"
            if success
            else f"Session {request.session_id} not found",
        }
    except Exception as e:
        logger.error(f"Error setting active session: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}


@server.tool()
async def get_screen(
    request: GetScreenRequest,
) -> Dict[str, Union[str, List[Dict[str, str]]]]:
    """Get the current screen contents of terminal sessions.

    This tool retrieves the visible content from terminal sessions. The behavior depends on the mode:

    - 'focus' (default): Gets content from the currently active session (set via set_active_session)
    - 'recent-output': Automatically finds the most recently active session and gets its content
    - 'manual': Uses the active session (same as focus mode)

    IMPORTANT: For 'focus' and 'manual' modes, you must first call set_active_session() to select
    which session to get content from.

    RECOMMENDED: For examining all sessions at once, use get_all_terminal_info() instead.

    Workflow for examining individual sessions:
    1. list_sessions() - get all available session IDs
    2. For each session you want to examine:
       a. set_active_session(session_id) - switch to that session
       b. get_screen() - get content from that session

    """
    try:
        if request.mode == "recent-output":
            # Find most recent TTY and map to session
            recent_tty = terminal_manager.get_most_recent_tty()
            if recent_tty:
                sessions = terminal_manager.scan_sessions()
                for session in sessions:
                    if session.tty_device == recent_tty:
                        session_id = f"{session.window_id}_{session.tab_id}"
                        terminal_manager.set_active_session(session_id)
                        content = terminal_manager.get_session_content(
                            session_id, request.lines
                        )
                        return {
                            "mode": "recent-output",
                            "content": content,
                            "session_id": session_id,
                        }

            return {"mode": "recent-output", "content": "No recent output found"}

        else:  # focus mode (default)
            if not terminal_manager.active_session_id:
                # Try to find the most recently active session
                sessions = terminal_manager.scan_sessions()
                if sessions:
                    most_recent = max(sessions, key=lambda s: s.last_activity)
                    session_id = f"{most_recent.window_id}_{most_recent.tab_id}"
                    terminal_manager.set_active_session(session_id)

            if terminal_manager.active_session_id:
                content = terminal_manager.get_active_session_content(request.lines)
                return {
                    "mode": "focus",
                    "content": content,
                    "session_id": terminal_manager.active_session_id,
                }
            else:
                return {"mode": "focus", "content": "No active session available"}

    except Exception as e:
        logger.error(f"Error getting screen content: {e}")
        return {"error": str(e)}


@server.tool()
async def send_input(request: SendInputRequest) -> Dict[str, Union[bool, str]]:
    """Send input (commands or keystrokes) to the terminal."""
    try:
        # Security: Check readonly mode
        if is_readonly_mode():
            logger.warning(
                "Input injection blocked: Server is running in readonly mode"
            )
            return {
                "success": False,
                "message": "Input injection is disabled. Set MCP_TERMINAL_READONLY=0 to enable.",
            }

        session_id = request.session_id or terminal_manager.active_session_id
        if not session_id:
            return {"success": False, "message": "No active session set"}

        success = terminal_manager.send_input(session_id, request.text, request.execute)
        return {
            "success": success,
            "message": f"Input sent to session {session_id}"
            if success
            else f"Failed to send input to session {session_id}",
        }
    except Exception as e:
        logger.error(f"Error sending input: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}


@server.tool()
async def send_keypress(request: SendKeypressRequest) -> Dict[str, Union[bool, str]]:
    """Send a specific keypress to the terminal."""
    try:
        # Security: Check readonly mode
        if is_readonly_mode():
            logger.warning(
                "Keypress injection blocked: Server is running in readonly mode"
            )
            return {
                "success": False,
                "message": "Input injection is disabled. Set MCP_TERMINAL_READONLY=0 to enable.",
            }

        session_id = request.session_id or terminal_manager.active_session_id
        if not session_id:
            return {"success": False, "message": "No active session set"}

        success = terminal_manager.send_keypress(
            session_id, request.key, request.modifiers
        )
        return {
            "success": success,
            "message": f"Keypress sent to session {session_id}"
            if success
            else f"Failed to send keypress to session {session_id}",
        }
    except Exception as e:
        logger.error(f"Error sending keypress: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}


@server.tool()
async def paste_text(request: PasteTextRequest) -> Dict[str, Union[bool, str]]:
    """Paste text into the terminal using clipboard."""
    try:
        # Security: Check readonly mode
        if is_readonly_mode():
            logger.warning("Text paste blocked: Server is running in readonly mode")
            return {
                "success": False,
                "message": "Input injection is disabled. Set MCP_TERMINAL_READONLY=0 to enable.",
            }

        session_id = request.session_id or terminal_manager.active_session_id
        if not session_id:
            return {"success": False, "message": "No active session set"}

        success = terminal_manager.paste_text(session_id, request.text)
        return {
            "success": success,
            "message": f"Text pasted to session {session_id}"
            if success
            else f"Failed to paste text to session {session_id}",
        }
    except Exception as e:
        logger.error(f"Error pasting text: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}


@server.tool()
async def scroll_back(request: ScrollBackRequest) -> Dict[str, str]:
    """Scroll back to get older content from the terminal buffer."""
    try:
        session_id = request.session_id or terminal_manager.active_session_id
        if not session_id:
            return {"content": "No active session set"}

        content = terminal_manager.scroll_back(session_id, request.pages)
        return {"content": content, "session_id": session_id}
    except Exception as e:
        logger.error(f"Error scrolling back: {e}")
        return {"content": f"Error: {str(e)}"}


@server.tool()
async def get_all_terminal_info(request: GetScreenRequest) -> Dict[str, Any]:
    """Get comprehensive information about all terminal sessions in one call.

    This tool returns everything you need to know about terminal sessions in a single response:
    - List of all session IDs
    - Content from each session
    - Default/current active session ID
    - Summary information

    This is the recommended tool to use when you want to examine all terminal sessions
    without making multiple sequential tool calls.

    Usage:
    - Call get_all_terminal_info() to get everything about all sessions
    - Use the returned session_ids list to know what sessions are available
    - Use the session_contents dict to get content for any session
    - Use the default_session_id to know which session is currently active

    This avoids the need for multiple sequential tool calls and provides all information
    in a single, comprehensive response.
    """
    try:
        logger.info("get_all_terminal_info tool called")

        # Get all sessions
        sessions = terminal_manager.scan_sessions()
        logger.info(f"Found {len(sessions)} sessions")

        # Extract session IDs
        session_ids = []
        session_contents = {}
        session_info = {}

        for session in sessions:
            session_id = f"{session.window_id}_{session.tab_id}"
            session_ids.append(session_id)

            # Get content for this session
            content = terminal_manager.get_session_content(session_id, request.lines)
            session_contents[session_id] = content

            # Store additional session info
            session_info[session_id] = {
                "name": session.name,
                "tty_device": session.tty_device,
                "is_active": session.is_active,
                "last_activity": session.last_activity,
            }

        # Determine default/current session
        default_session_id = None
        if terminal_manager.active_session_id:
            default_session_id = terminal_manager.active_session_id
        elif session_ids:
            # If no active session, use the most recently active one
            most_recent = max(sessions, key=lambda s: s.last_activity)
            default_session_id = f"{most_recent.window_id}_{most_recent.tab_id}"

        # Create comprehensive response
        response = {
            "session_ids": session_ids,
            "session_contents": session_contents,
            "session_info": session_info,
            "default_session_id": default_session_id,
            "total_sessions": len(sessions),
            "summary": f"Found {len(sessions)} terminal sessions. Default session: {default_session_id}",
        }

        logger.info(f"Returning comprehensive info for {len(sessions)} sessions")
        return response

    except Exception as e:
        logger.error(f"Error getting all terminal info: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "session_ids": [],
            "session_contents": {},
            "session_info": {},
            "default_session_id": None,
            "total_sessions": 0,
            "summary": f"Error: {str(e)}",
        }


if __name__ == "__main__":
    import sys

    print("Starting Terminal MCP Server (stdio transport)...", file=sys.stderr)
    print("This server is ready to communicate via stdin/stdout", file=sys.stderr)
    logger.info("Starting server with stdio transport")
    server.run(transport="stdio")
