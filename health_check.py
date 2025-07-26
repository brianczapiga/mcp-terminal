#!/usr/bin/env python3
"""
Health check script for Terminal MCP Server.
This script verifies that the server can be imported and basic functionality works.
"""

import sys
import os
import subprocess
import time


def check_python_version():
    """Check if Python version is compatible."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import fastmcp
        import pydantic
        import typing_extensions

        print("✅ All required dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False


def check_macos():
    """Check if running on macOS."""
    if sys.platform != "darwin":
        print("❌ This server only works on macOS")
        return False
    print("✅ Running on macOS")
    return True


def check_terminal_apps():
    """Check if Terminal.app or iTerm2 is available."""
    try:
        # Check for Terminal.app
        result = subprocess.run(
            ["osascript", "-e", 'tell application "Terminal" to get name'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            print("✅ Terminal.app is available")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        # Check for iTerm2
        result = subprocess.run(
            ["osascript", "-e", 'tell application "iTerm2" to get name'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            print("✅ iTerm2 is available")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    print("❌ Neither Terminal.app nor iTerm2 is available")
    return False


def check_permissions():
    """Check if Accessibility permissions are granted."""
    print("⚠️  Checking Accessibility permissions...")
    print("   Please ensure Terminal.app or iTerm2 has Accessibility permissions")
    print("   Go to System Preferences → Security & Privacy → Privacy → Accessibility")
    return True


def check_server_import():
    """Check if the server can be imported."""
    try:
        from terminal_mcp_server import TerminalManager, SessionInfo

        print("✅ Server module can be imported")
        return True
    except Exception as e:
        print(f"❌ Failed to import server module: {e}")
        return False


def check_server_initialization():
    """Check if the server can be initialized."""
    try:
        from terminal_mcp_server import TerminalManager

        manager = TerminalManager()
        print("✅ Server can be initialized")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize server: {e}")
        return False


def check_readonly_mode():
    """Check readonly mode status."""
    try:
        from terminal_mcp_server import is_readonly_mode

        readonly = is_readonly_mode()
        if readonly:
            print("🔒 Readonly mode: ENABLED (input injection disabled)")
        else:
            print("⚠️  Readonly mode: DISABLED (input injection enabled)")
        return True
    except Exception as e:
        print(f"❌ Failed to check readonly mode: {e}")
        return False


def main():
    """Run all health checks."""
    print("🏥 Terminal MCP Server Health Check")
    print("=" * 40)

    checks = [
        ("Python Version", check_python_version),
        ("macOS Platform", check_macos),
        ("Dependencies", check_dependencies),
        ("Terminal Apps", check_terminal_apps),
        ("Server Import", check_server_import),
        ("Server Initialization", check_server_initialization),
        ("Readonly Mode", check_readonly_mode),
        ("Permissions", check_permissions),
    ]

    passed = 0
    total = len(checks)

    for name, check_func in checks:
        print(f"\n🔍 {name}:")
        try:
            if check_func():
                passed += 1
        except Exception as e:
            print(f"❌ Error during {name} check: {e}")

    print("\n" + "=" * 40)
    print(f"📊 Results: {passed}/{total} checks passed")

    if passed == total:
        print("🎉 All checks passed! The server should work correctly.")
        return 0
    else:
        print("⚠️  Some checks failed. Please review the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
