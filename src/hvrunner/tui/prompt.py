"""Single line modal input."""

from __future__ import annotations

import contextlib
import curses
from dataclasses import dataclass
from typing import Any

from .editline import EditLine, scroll_offset
from .text import fit
from .theme import Theme
from .widgets import draw_text

MINIMUM_WIDTH = 24
MINIMUM_HEIGHT = 7

BOX_HEIGHT = 5

# Terminals disagree about backspace: kitty sends DEL, others send ^H, and
# ncurses only folds either onto KEY_BACKSPACE once keypad translation is on.
# Accepting all three means the field erases whatever terminfo says.
BACKSPACE = (curses.KEY_BACKSPACE, 8, 127)
ESCAPE = 27
RETURN = (10, 13, curses.KEY_ENTER)

# Readline's control keys, which cost nothing to support and are what anyone
# editing a long path in a terminal reaches for.
START_KEYS = (curses.KEY_HOME, 1)
END_KEYS = (curses.KEY_END, 5)
KILL_TO_START = 21
KILL_WORD = 23

# ncurses waits a full second to decide whether an escape byte begins a
# sequence, which makes cancelling feel broken. Process wide, so set once.
ESCAPE_DELAY_MS = 25

TAB = 9

HINT = "^w word  ^u clear  esc cancel"
BROWSE_HINT = "tab browse  ^w word  esc cancel"


@dataclass(frozen=True)
class Browse:
    """Returned in place of a value when the browser was asked for.

    It carries what had been typed so far, so opening the browser can start
    from the deepest part of that which exists rather than discarding it.
    """

    text: str


def _apply(line: EditLine, code: int) -> None:
    """Act on a key that is not text, an accept or a cancel."""
    if code in BACKSPACE:
        line.backspace()
    elif code == curses.KEY_DC:
        line.delete()
    elif code == curses.KEY_LEFT:
        line.move(-1)
    elif code == curses.KEY_RIGHT:
        line.move(1)
    elif code in START_KEYS:
        line.to_start()
    elif code in END_KEYS:
        line.to_end()
    elif code == KILL_TO_START:
        line.kill_to_start()
    elif code == KILL_WORD:
        line.kill_word()


def _draw(
    window: Any, theme: Theme, label: str, width: int, line: EditLine, offset: int, field: int, hint: str
) -> None:
    window.erase()
    with contextlib.suppress(curses.error):
        window.border()
    inner = width - 4
    draw_text(window, 1, 2, fit(label, inner), inner, theme.attr("label"))
    draw_text(window, 2, 2, line.text[offset : offset + field], field, theme.attr("text"))
    # Text wider than the field scrolls rather than being cut, so mark which way
    # it continues instead of letting a fragment look like the whole value.
    more = theme.glyph("ellipsis")[:1]
    if offset:
        draw_text(window, 2, 1, more, 1, theme.attr("rule"))
    if len(line.text) > offset + field:
        draw_text(window, 2, width - 2, more, 1, theme.attr("rule"))
    draw_text(window, 3, 2, fit(hint, inner), inner, theme.attr("rule"))
    with contextlib.suppress(curses.error):
        window.move(2, 2 + line.cursor - offset)
    window.refresh()


def ask(screen: Any, theme: Theme, label: str, initial: str = "", browsable: bool = False) -> str | Browse | None:
    """Return the entered text, or None when cancelled or there is no room.

    An empty field returns "", not None. The two have to be told apart or a
    stored value could be set and never cleared.

    With browsable set, tab returns Browse instead, and the caller is expected
    to run the file browser and come back.
    """
    height, width = screen.getmaxyx()
    if width < MINIMUM_WIDTH or height < MINIMUM_HEIGHT:
        return None
    with contextlib.suppress(AttributeError, curses.error):
        curses.set_escdelay(ESCAPE_DELAY_MS)

    box_width = min(max(40, len(label) + 8), max(20, width - 4))
    top = max(0, min(height // 2 - 2, height - BOX_HEIGHT))
    left = max(0, (width - box_width) // 2)
    window = curses.newwin(BOX_HEIGHT, box_width, top, left)
    window.bkgd(" ", theme.attr("text"))
    # Without this the terminal's own backspace and arrow sequences arrive as
    # raw bytes and land in the buffer as symbols. stdscr having keypad set says
    # nothing about a window created after it.
    window.keypad(True)

    field = max(1, box_width - 4)
    hint = BROWSE_HINT if browsable else HINT
    line = EditLine(initial)
    offset = 0
    curses.curs_set(1)
    try:
        while True:
            offset = scroll_offset(line.cursor, field, offset)
            _draw(window, theme, label, box_width, line, offset, field, hint)
            try:
                key = window.get_wch()
            except curses.error:
                continue
            # get_wch returns a string for anything the terminal calls text,
            # which is what keeps a non-ASCII path intact.
            if isinstance(key, str) and key.isprintable():
                line.insert(key)
                continue
            code = ord(key) if isinstance(key, str) else key
            if code in RETURN:
                break
            if code == ESCAPE:
                return None
            if code == TAB and browsable:
                return Browse(line.text.strip())
            _apply(line, code)
    finally:
        curses.curs_set(0)
        del window
        screen.touchwin()
    return line.text.strip()
