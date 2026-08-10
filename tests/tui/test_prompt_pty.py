"""The path field, driven through a real terminal.

Everything here failed before prompt.ask stopped using curses.getstr. They are
marked integration and excluded from ./bin/check because each one spends a
couple of seconds waiting on a pty.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

# A terminal sends DEL for backspace, not ^H, and ncurses only folds it onto
# KEY_BACKSPACE once keypad translation is on. keypad(True) also puts the
# terminal into application mode, where the arrows are ESC O x rather than
# ESC [ x. Sending the wrong form reads as a bare escape, which cancels.
DEL = b"\x7f"
LEFT = b"\x1bOD"
HOME = b"\x1bOH"
KILL_WORD = b"\x17"
ESCAPE = b"\x1b"
ENTER = b"\r"

LONG_PATH = "/mnt/data/games/Hitman-Absolution-AnkerGames/Hitman Absolution/HMA.exe"

PROGRAM = """
import curses, os, sys
sys.path.insert(0, os.environ["PTY_SRC"])
from hvrunner.tui.prompt import ask
from hvrunner.tui.theme import Theme

def main(screen):
    theme = Theme()
    theme.setup()
    return ask(screen, theme, "Path to a Windows executable")

value = curses.wrapper(main)
with open(os.environ["PTY_OUT"], "w") as handle:
    handle.write(repr(value))
"""


def test_a_path_longer_than_the_field_is_kept(pty_run):
    """getstr capped the value at the width of the box, which is about 36 columns."""
    assert pty_run(PROGRAM, [LONG_PATH.encode(), ENTER]) == repr(LONG_PATH)


def test_backspace_deletes_rather_than_inserting_a_symbol(pty_run):
    assert pty_run(PROGRAM, [LONG_PATH.encode() + b"XYZ", DEL * 3, ENTER]) == repr(LONG_PATH)


def test_the_left_arrow_moves_the_cursor(pty_run):
    assert pty_run(PROGRAM, [b"/mnt/gams", LEFT, b"e", ENTER]) == repr("/mnt/games")


def test_home_jumps_to_the_start(pty_run):
    assert pty_run(PROGRAM, [b"mnt/data", HOME, b"/", ENTER]) == repr("/mnt/data")


def test_kill_word_removes_one_folder(pty_run):
    assert pty_run(PROGRAM, [b"/mnt/data/games", KILL_WORD, b"logs", ENTER]) == repr("/mnt/data/logs")


def test_escape_cancels(pty_run):
    assert pty_run(PROGRAM, [b"/mnt/data", ESCAPE]) == repr(None)
