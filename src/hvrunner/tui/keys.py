"""Key matching, and the raw codes behind it, in one place.

Four screens each need "down", "up", "confirm" and "leave", and the prompt needs
the codes themselves. Spelling either out at the call site is where bindings
drift: the prompt and the browser each grew a private idea of what backspace is,
and the two disagreed with this module about what enter meant.
"""

from __future__ import annotations

import curses

ESCAPE = 27
TAB = 9

# Terminals disagree about backspace: kitty sends DEL, others send ^H, and
# ncurses only folds either onto KEY_BACKSPACE once keypad translation is on.
# Accepting all three means a field erases whatever terminfo says.
BACKSPACE = (curses.KEY_BACKSPACE, 8, 127)
RETURN = (10, 13, curses.KEY_ENTER)

# Readline's control keys, which cost nothing to support and are what anyone
# editing a long path in a terminal reaches for.
START_KEYS = (curses.KEY_HOME, 1)
END_KEYS = (curses.KEY_END, 5)
KILL_TO_START = 21
KILL_WORD = 23


def is_down(key: int) -> bool:
    return key in (curses.KEY_DOWN, ord("j"))


def is_up(key: int) -> bool:
    return key in (curses.KEY_UP, ord("k"))


def is_left(key: int) -> bool:
    return key in (curses.KEY_LEFT, ord("h"))


def is_confirm(key: int) -> bool:
    return key in RETURN


def is_leave(key: int) -> bool:
    return key in (ESCAPE, ord("q"))


def is_back(key: int) -> bool:
    """Go up a level: what a shell has trained everyone to reach for."""
    return is_left(key) or key in BACKSPACE


def is_page_down(key: int) -> bool:
    return key == curses.KEY_NPAGE


def is_page_up(key: int) -> bool:
    return key == curses.KEY_PPAGE
