from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hvrunner.core.config import default_config  # noqa: E402


@pytest.fixture
def state_home(tmp_path, monkeypatch):
    """Redirect log output away from the real state directory."""
    root = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(root))
    return root


@pytest.fixture
def fake_proton(tmp_path):
    proton = tmp_path / "Proton"
    proton.mkdir()
    (proton / "proton").write_text("stub")
    (proton / "toolmanifest.vdf").write_text("stub")
    return proton


@pytest.fixture
def fake_umu(tmp_path):
    umu = tmp_path / "umu-run"
    umu.write_text("stub")
    return umu


@pytest.fixture
def game_dir(tmp_path):
    folder = tmp_path / "BFResynced"
    folder.mkdir()
    (folder / "ACBlackFlag.exe").write_text("stub")
    return folder


@pytest.fixture
def config(fake_proton, fake_umu, tmp_path):
    values = default_config()
    values.update(
        {
            "proton_path": str(fake_proton),
            "umu_path": str(fake_umu),
            "library_roots": [str(tmp_path)],
        }
    )
    return values


@pytest.fixture
def stub_tools(monkeypatch):
    """Make MangoHud and gamemode lookups deterministic."""
    import hvrunner.core.planning as planning

    def which(name):
        return f"/usr/bin/{name}" if name in {"mangohud", "gamemoderun"} else None

    monkeypatch.setattr(planning.shutil, "which", which)


@pytest.fixture
def game_factory(tmp_path):
    """Build a game folder with an executable of a given name."""

    def make(name: str = "ACBlackFlag.exe", folder: str = "G"):
        from hvrunner.core.constants import CUSTOM_SOURCE
        from hvrunner.core.models import Game

        directory = tmp_path / folder
        directory.mkdir(parents=True, exist_ok=True)
        executable = directory / name
        executable.write_text("stub")
        return Game(directory.name, CUSTOM_SOURCE, str(directory), str(executable))

    return make


@pytest.fixture
def pty_run(tmp_path):
    """Run a small curses program under a real pty and return what it produced.

    The prompt and the browser cannot be exercised any other way. The two bugs
    they shipped with were a window that never had keypad translation enabled
    and a length cap inside curses.getstr, and neither is visible to a fake
    screen: both live in what the terminal and ncurses do to the bytes.

    The program is given PTY_SRC to import from and PTY_OUT to write its repr
    to. Keystrokes arrive as a list of chunks with a pause between them, so a
    screen has drawn before the next key lands.
    """
    import fcntl
    import os
    import pty
    import struct
    import subprocess
    import sys
    import termios
    import time

    source_root = str(Path(__file__).resolve().parents[1] / "src")

    def run(program: str, chunks: list[bytes], timeout: float = 30.0) -> str:
        out = tmp_path / "pty-result.txt"
        primary, secondary = pty.openpty()
        # A fixed size, so a layout that depends on width cannot make the test
        # depend on whatever terminal happens to be running it.
        fcntl.ioctl(secondary, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
        child = subprocess.Popen(
            [sys.executable, "-c", program],
            stdin=secondary,
            stdout=secondary,
            stderr=secondary,
            env={
                **os.environ,
                "TERM": "xterm-256color",
                "LANG": "en_US.UTF-8",
                "PTY_SRC": source_root,
                "PTY_OUT": str(out),
            },
            close_fds=True,
        )
        os.close(secondary)
        try:
            time.sleep(1.5)  # let curses finish initialising before typing
            for chunk in chunks:
                os.write(primary, chunk)
                time.sleep(0.35)
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            child.kill()
            raise AssertionError("the curses program never exited; a key was probably not consumed") from None
        finally:
            os.close(primary)
        return out.read_text() if out.exists() else ""

    return run
