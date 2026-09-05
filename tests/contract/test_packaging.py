from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path


def test_wheel_contains_runtime_and_console_entry_point(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(tmp_path),
        ],
        check=True,
    )
    wheel = next(tmp_path.glob("*.whl"))

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        expected_modules = {
            "terminal_mcp/server.py",
            "terminal_mcp/manager.py",
            "terminal_mcp/config.py",
            "terminal_mcp/backends/base.py",
        }
        assert expected_modules <= names
        entry_points_name = next(
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        )
        entry_points = archive.read(entry_points_name).decode()
        assert "terminal-mcp-server = terminal_mcp.server:main" in entry_points

    smoke = """
from importlib.metadata import entry_points
import terminal_mcp
import terminal_mcp.server

assert terminal_mcp.__version__ == "2.0.0"
entry_point = next(ep for ep in entry_points(group="console_scripts")
                   if ep.name == "terminal-mcp-server")
assert entry_point.value == "terminal_mcp.server:main"
"""
    environment = os.environ | {"PYTHONPATH": str(wheel)}
    subprocess.run(
        [sys.executable, "-c", smoke], check=True, cwd=tmp_path, env=environment
    )
