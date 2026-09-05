from __future__ import annotations

import os
import subprocess
import sys
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

    venv = tmp_path / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", "--system-site-packages", str(venv)],
        check=True,
    )
    python = venv / "bin" / "python"
    subprocess.run([python, "-m", "pip", "install", "--no-deps", wheel], check=True)
    smoke = """
import sys
from importlib.metadata import distribution
from pathlib import Path
from sysconfig import get_path

sys.path.insert(0, get_path("purelib"))
import terminal_mcp

dist = distribution("terminal-mcp-server")
entry_point = next(ep for ep in dist.entry_points
                   if ep.name == "terminal-mcp-server")
assert dist.version == terminal_mcp.__version__
assert callable(entry_point.load())
assert Path(terminal_mcp.__file__).is_relative_to(Path(sys.prefix))
"""
    import fastmcp

    dependency_path = str(Path(fastmcp.__file__).parents[1])
    subprocess.run(
        [python, "-c", smoke],
        check=True,
        cwd=tmp_path,
        env=os.environ | {"PYTHONPATH": dependency_path},
    )
    assert (venv / "bin" / "terminal-mcp-server").is_file()
