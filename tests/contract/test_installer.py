import os
import shutil
import subprocess
import sys
from pathlib import Path


def test_installer_anchors_files_to_checkout_and_preserves_env(tmp_path: Path) -> None:
    project = tmp_path / "project"
    caller = tmp_path / "caller"
    fake_bin = tmp_path / "bin"
    for directory in (project, caller, fake_bin):
        directory.mkdir()
    shutil.copy("install.sh", project)
    (project / "env.example").write_text("MCP_TERMINAL_READONLY=1\n")
    log = tmp_path / "uv.log"
    (fake_bin / "python3").symlink_to(sys.executable)
    commands = {
        "uname": "#!/bin/sh\necho Darwin\n",
        "uv": '#!/bin/sh\npwd >> "$UV_LOG"\nprintf "%s\\n" "$*" >> "$UV_LOG"\n',
    }
    for name, contents in commands.items():
        command = fake_bin / name
        command.write_text(contents)
        command.chmod(0o755)
    env = os.environ | {"PATH": f"{fake_bin}:{os.environ['PATH']}", "UV_LOG": str(log)}

    subprocess.run([project / "install.sh"], cwd=caller, env=env, check=True)
    assert ((project / ".env").read_text(), (caller / ".env").exists()) == (
        "MCP_TERMINAL_READONLY=1\n",
        False,
    )
    (project / ".env").write_text("MCP_TERMINAL_READONLY=0\n")
    subprocess.run([project / "install.sh"], cwd=caller, env=env, check=True)
    assert (project / ".env").read_text() == "MCP_TERMINAL_READONLY=0\n"
    assert log.read_text().splitlines()[::2] == [str(project), str(project)] * 2
