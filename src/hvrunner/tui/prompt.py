"""Single line modal input."""

from __future__ import annotations

import contextlib
import curses
from typing import Any

from .text import fit
from .theme import Theme
from .widgets import draw_text

MINIMUM_WIDTH = 24
MINIMUM_HEIGHT = 7


def ask(screen: Any, theme: Theme, label: str, initial: str = "") -> str | None:
    """Return the entered text, or None when cancelled or there is no room."""
    height, width = screen.getmaxyx()
    if width < MINIMUM_WIDTH or height < MINIMUM_HEIGHT:
        return None

    box_width = min(max(40, len(label) + 8), max(20, width - 4))
    top = max(0, height // 2 - 2)
    left = max(0, (width - box_width) // 2)
    window = curses.newwin(4, box_width, top, left)
    window.bkgd(" ", theme.attr("text"))
    window.erase()
    with contextlib.suppress(curses.error):
        window.border()

    field_width = box_width - 4
    draw_text(window, 1, 2, fit(label, box_width - 4), box_width - 4, theme.attr("label"))
    draw_text(window, 2, 2, initial[:field_width], field_width, theme.attr("text"))
    window.refresh()

    curses.echo()
    curses.curs_set(1)
    try:
        raw = window.getstr(2, 2, field_width)
        value = raw.decode(errors="replace").strip() if raw else ""
    except curses.error:
        value = ""
    finally:
        curses.noecho()
        curses.curs_set(0)
        del window
        screen.touchwin()
    return value or None
