"""The file browser, driven through a real terminal.

Covers the loop between App.prompt_path, the prompt and BrowseScreen, which no
unit test can reach: the prompt returns a Browse sentinel and app runs the
screen, so the handoff only exists when a terminal is driving it.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

TAB = b"\t"
ESCAPE = b"\x1b"
ENTER = b"\r"
DOWN = b"j"

PROGRAM = """
import curses, os, sys
from pathlib import Path
sys.path.insert(0, os.environ["PTY_SRC"])
from hvrunner.core.browsing import Want
from hvrunner.core.config import default_config
from hvrunner.tui.app import App

def main(screen):
    config = default_config()
    config["library_roots"] = [os.environ["PTY_ROOT"]]
    config["custom_games"] = []
    app = App(screen, config, Path(os.environ["PTY_ROOT"]) / "unused-config.json")
    return app.prompt_path("Pick one", Want.%s)

value = curses.wrapper(main)
with open(os.environ["PTY_OUT"], "w") as handle:
    handle.write(repr(value))
"""


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A library root the browser opens on.

    Aardvark sorts before Hitman, so the listing is ["..", "Aardvark/",
    "Hitman/"] and reaching Hitman takes two moves. notes.txt is here to be
    filtered out when an executable is what is wanted.
    """
    root = tmp_path / "library"
    (root / "Hitman" / "data").mkdir(parents=True)
    (root / "Aardvark").mkdir(parents=True)
    (root / "Hitman" / "HMA.exe").write_text("stub")
    (root / "Hitman" / "notes.txt").write_text("stub")
    monkeypatch.setenv("PTY_ROOT", str(root))
    return root


def test_tab_opens_the_browser_and_a_file_can_be_picked(pty_run, tree):
    # Two moves to Hitman/, enter to descend, two more to HMA.exe past "../"
    # and "data/", enter to take it.
    result = pty_run(PROGRAM % "EXECUTABLE", [TAB, DOWN * 2, ENTER, DOWN * 2, ENTER])
    assert result == repr(str(tree / "Hitman" / "HMA.exe"))


def test_directory_mode_takes_the_current_folder(pty_run, tree):
    result = pty_run(PROGRAM % "DIRECTORY", [TAB, DOWN * 2, ENTER, b"s"])
    assert result == repr(str(tree / "Hitman"))


def test_leaving_the_browser_keeps_what_was_typed(pty_run, tree):
    result = pty_run(PROGRAM % "DIRECTORY", [b"/mnt/da", TAB, ESCAPE, b"ta", ENTER])
    assert result == repr("/mnt/data")


def test_typing_a_path_without_the_browser_still_works(pty_run, tree):
    result = pty_run(PROGRAM % "DIRECTORY", [b"/mnt/data/games", ENTER])
    assert result == repr("/mnt/data/games")
