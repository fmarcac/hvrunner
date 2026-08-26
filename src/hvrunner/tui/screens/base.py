"""Shared screen loops.

Every screen is draw, read a key, decide whether to stay. Keeping that in one
place is what stops the screens from drifting apart in how they redraw and how
they handle a resize.
"""

from __future__ import annotations

import curses
from typing import TYPE_CHECKING

from .. import keys, layout
from ..text import letterspace
from ..widgets import Painter, Rect

if TYPE_CHECKING:
    from ..app import App


class Screen:
    #: When set, getch times out after this many milliseconds so the screen can
    #: redraw on its own. Used by the log feed to follow a growing file.
    poll_interval: int | None = None

    def __init__(self, app: App):
        self.app = app
        self.paint: Painter = app.paint

    # ---- to override --------------------------------------------------------

    def refresh_data(self) -> None:
        """Called before every draw."""

    def draw(self) -> Rect:
        raise NotImplementedError

    def handle(self, key: int) -> bool:
        """Return False to leave this screen."""
        raise NotImplementedError

    # ---- loop ---------------------------------------------------------------

    def run(self) -> None:
        screen = self.app.screen
        while True:
            # Re-asserted every pass rather than set once on entry. There is one
            # stdscr, so a nested screen's interval outlives the screen that set
            # it: a log feed opened from the library used to leave the library
            # blocking on getch, and a screen with no interval of its own used to
            # inherit one and redraw for no reason.
            screen.timeout(self.poll_interval or -1)
            self.refresh_data()
            screen.erase()
            self.draw()
            screen.refresh()
            key = screen.getch()
            # -1 is a poll timeout, KEY_RESIZE only needs a redraw.
            if key in (-1, curses.KEY_RESIZE):
                continue
            if not self.handle(key):
                return


class ListDetailScreen(Screen):
    """A list on the left, and what the cursor is on to the right.

    The settings screen, the entry editor, the post-install picker and the file
    browser were four copies of this: the same split, the same divider, the same
    modulo cursor, and the same three-part test for whether there was room for a
    detail pane, written out four times.
    """

    title = ""
    footer = ""
    empty_message = "Nothing here."
    min_list = 22
    max_list = 34

    def __init__(self, app: App):
        super().__init__(app)
        self.cursor = 0

    # ---- to override --------------------------------------------------------

    def labels(self) -> list[str]:
        raise NotImplementedError

    def meta(self) -> str:
        """What goes in the top rule, to the right of the title."""
        return ""

    def footer_text(self) -> str:
        return self.footer

    def draw_detail(self, area: Rect) -> None:
        """The right hand pane. Nothing by default."""

    def draw_status(self, inner: Rect) -> None:
        self.paint.status(inner, self.app.status)

    def confirm(self) -> bool:
        """Enter. Return False to leave the screen."""
        return True

    def leave(self) -> bool:
        """Escape or q. Return False to leave the screen, which is the default."""
        return False

    def extra(self, key: int) -> bool | None:
        """A binding this screen alone has. None means "not mine"."""
        return None

    # ---- shared -------------------------------------------------------------

    def move(self, step: int) -> None:
        count = len(self.labels())
        if count:
            self.cursor = (self.cursor + step) % count

    def draw(self) -> Rect:
        inner = self.paint.frame(letterspace(self.title), self.meta(), self.footer_text())
        if inner.height < 4:
            return inner
        panes = layout.split(inner, min_list=self.min_list, max_list=self.max_list)
        labels = self.labels()
        if labels:
            self.paint.rows(panes.items, labels, self.cursor)
        else:
            self.paint.text(panes.items.top, panes.items.left, self.empty_message, panes.items.width, "label")
        if panes.split and panes.detail and panes.divider_x is not None:
            self.paint.divider(panes.divider_x, inner.top, inner.height - 1)
            self.draw_detail(panes.detail)
        self.draw_status(inner)
        return inner

    def handle(self, key: int) -> bool:
        if keys.is_leave(key):
            return self.leave()
        handled = self.extra(key)
        if handled is not None:
            return handled
        if keys.is_down(key):
            self.move(1)
        elif keys.is_up(key):
            self.move(-1)
        elif keys.is_confirm(key):
            return self.confirm()
        return True
