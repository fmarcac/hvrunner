"""Key matching, in one place.

Three screens each need "down", "up", "confirm" and "leave". Spelling the tuples
out at every call site is where inconsistent bindings creep in.
"""

from __future__ import annotations

import curses

ESCAPE = 27
RETURN = (10, 13)


def is_down(key: int) -> bool:
    return key in (curses.KEY_DOWN, ord("j"))


def is_up(key: int) -> bool:
    return key in (curses.KEY_UP, ord("k"))


def is_confirm(key: int) -> bool:
    return key in (*RETURN, curses.KEY_ENTER)


def is_leave(key: int) -> bool:
    return key in (ESCAPE, ord("q"))


def is_page_down(key: int) -> bool:
    return key == curses.KEY_NPAGE


def is_page_up(key: int) -> bool:
    return key == curses.KEY_PPAGE
