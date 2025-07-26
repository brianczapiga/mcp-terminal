"""
Tests for the Terminal MCP Server.
"""

import pytest
from unittest.mock import Mock, patch
from terminal_mcp_server import TerminalManager, SessionInfo


class TestTerminalManager:
    """Test cases for TerminalManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = TerminalManager()

    def test_detect_terminal_app(self):
        """Test terminal app detection."""
        with patch.object(self.manager, "_run_applescript") as mock_run:
            # Test iTerm2 detection
            mock_run.return_value = "iTerm2"
            result = self.manager._detect_terminal_app()
            assert result == "iTerm2"

            # Test fallback to Terminal
            mock_run.return_value = "Terminal"
            result = self.manager._detect_terminal_app()
            assert result == "Terminal"

    def test_run_applescript_success(self):
        """Test successful AppleScript execution."""
        with patch("subprocess.run") as mock_run:
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.stdout = b"test output"
            mock_run.return_value = mock_process

            result = self.manager._run_applescript("test script")
            assert result == "test output"

    def test_run_applescript_failure(self):
        """Test AppleScript execution failure."""
        with patch("subprocess.run") as mock_run:
            mock_process = Mock()
            mock_process.returncode = 1
            mock_process.stderr = b"error message"
            mock_run.return_value = mock_process

            result = self.manager._run_applescript("test script")
            assert result == ""

    @patch.object(TerminalManager, "_run_applescript")
    def test_scan_sessions(self, mock_run_applescript):
        """Test session scanning."""
        # Mock AppleScript response for session scanning
        mock_run_applescript.return_value = "session1,session2"

        sessions = self.manager.scan_sessions()
        assert isinstance(sessions, list)

    def test_get_session_content(self):
        """Test getting session content."""
        # Add a mock session
        session_info = SessionInfo(
            window_id="1",
            tab_id="1",
            name="Test Session",
            tty_device="/dev/ttys000",
            last_activity=1234567890.0,
            is_active=True,
        )
        self.manager.sessions["test_session"] = session_info

        with patch.object(self.manager, "_run_applescript") as mock_run:
            mock_run.return_value = "test content"
            content = self.manager.get_session_content("test_session", lines=10)
            assert content == "test content"

    def test_send_input(self):
        """Test sending input to a session."""
        # Add a mock session
        session_info = SessionInfo(
            window_id="1",
            tab_id="1",
            name="Test Session",
            tty_device="/dev/ttys000",
            last_activity=1234567890.0,
            is_active=True,
        )
        self.manager.sessions["test_session"] = session_info

        with patch.object(self.manager, "_run_applescript") as mock_run:
            mock_run.return_value = "success"
            result = self.manager.send_input("test_session", "ls -la", execute=True)
            assert result is True

    def test_set_active_session(self):
        """Test setting active session."""
        # Add a mock session
        session_info = SessionInfo(
            window_id="1",
            tab_id="1",
            name="Test Session",
            tty_device="/dev/ttys000",
            last_activity=1234567890.0,
            is_active=False,
        )
        self.manager.sessions["test_session"] = session_info

        result = self.manager.set_active_session("test_session")
        assert result is True
        assert self.manager.active_session_id == "test_session"

    def test_set_active_session_invalid(self):
        """Test setting invalid active session."""
        result = self.manager.set_active_session("invalid_session")
        assert result is False

    def test_scroll_back(self):
        """Test scroll back functionality."""
        # Add a mock session
        session_info = SessionInfo(
            window_id="1",
            tab_id="1",
            name="Test Session",
            tty_device="/dev/ttys000",
            last_activity=1234567890.0,
            is_active=True,
        )
        self.manager.sessions["test_session"] = session_info

        with patch.object(self.manager, "_run_applescript") as mock_run:
            mock_run.return_value = "scrolled content"
            content = self.manager.scroll_back("test_session", pages=1)
            assert content == "scrolled content"


class TestSessionInfo:
    """Test cases for SessionInfo dataclass."""

    def test_session_info_creation(self):
        """Test SessionInfo object creation."""
        session = SessionInfo(
            window_id="1",
            tab_id="1",
            name="Test Session",
            tty_device="/dev/ttys000",
            last_activity=1234567890.0,
            is_active=True,
        )

        assert session.window_id == "1"
        assert session.tab_id == "1"
        assert session.name == "Test Session"
        assert session.tty_device == "/dev/ttys000"
        assert session.last_activity == 1234567890.0
        assert session.is_active is True

    def test_session_info_without_tty(self):
        """Test SessionInfo creation without TTY device."""
        session = SessionInfo(
            window_id="1",
            tab_id="1",
            name="Test Session",
            tty_device=None,
            last_activity=1234567890.0,
            is_active=False,
        )

        assert session.tty_device is None
        assert session.is_active is False


# Integration tests (marked as slow)
@pytest.mark.slow
class TestIntegration:
    """Integration tests that require actual terminal interaction."""

    @pytest.mark.skipif(True, reason="Requires actual terminal interaction")
    def test_real_terminal_detection(self):
        """Test real terminal app detection."""
        manager = TerminalManager()
        app = manager._detect_terminal_app()
        assert app in ["Terminal", "iTerm2"]

    @pytest.mark.skipif(True, reason="Requires actual terminal interaction")
    def test_real_session_scanning(self):
        """Test real session scanning."""
        manager = TerminalManager()
        sessions = manager.scan_sessions()
        assert isinstance(sessions, list)


if __name__ == "__main__":
    pytest.main([__file__])
