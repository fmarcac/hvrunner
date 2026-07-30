"""Shared screen loop.

Every screen is draw, read a key, decide whether to stay. Keeping that in one
place is what stops the three screens from drifting apart in how they redraw and
how they handle a resize.
"""

from __future__ import annotations

import curses
from typing import TYPE_CHECKING

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
        if self.poll_interval:
            screen.timeout(self.poll_interval)
        try:
            while True:
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
        finally:
            if self.poll_interval:
                screen.timeout(-1)
