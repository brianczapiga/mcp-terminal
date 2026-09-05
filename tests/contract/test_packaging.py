from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile


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
    with ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "terminal_mcp/server.py" in names
        entry_points = next(
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        )
        contents = archive.read(entry_points).decode()
        assert "terminal-mcp-server = terminal_mcp.server:main" in contents
