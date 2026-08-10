"""File browser for a path prompt.

The prompt does not open this itself. Screens do not import one another and the
prompt is not a screen, so app is where the two meet: it runs the prompt, sees
that the browser was asked for, runs this, and feeds the result back.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...core.browsing import Want, human_size, listing
from .. import keys, layout
from ..text import fit, letterspace, shorten_path
from ..widgets import Rect
from .base import Screen

if TYPE_CHECKING:
    from ..app import App

# Backspace as "go up" costs nothing and is what a shell has trained everyone
# to reach for. The raw codes are here for the same reason prompt lists them.
BACK_KEYS = (8, 127)

PICK_DIRECTORY = ord("s")

FILE_KEYS = "j k move   enter open or pick   h backspace up   esc cancel"
DIRECTORY_KEYS = "j k move   enter open   h backspace up   s use this folder   esc cancel"


class BrowseScreen(Screen):
    def __init__(self, app: App, directory: Path, want: Want):
        super().__init__(app)
        self.want = want
        self.chosen: Path | None = None
        self.directory = directory
        self.entries = listing(directory, want)
        self.cursor = 0

    # ---- state --------------------------------------------------------------

    def _load(self, directory: Path, keep: str = "") -> None:
        """List a directory, landing the cursor on keep when it is present.

        Going up puts the cursor back on the folder just left, so walking a tree
        does not lose your place every time you change your mind.
        """
        self.directory = directory
        self.entries = listing(directory, self.want)
        self.cursor = 0
        if not keep:
            return
        for index, entry in enumerate(self.entries):
            if not entry.is_parent and entry.path.name == keep:
                self.cursor = index
                return

    def _up(self) -> None:
        parent = self.directory.parent
        if parent != self.directory:
            self._load(parent, keep=self.directory.name)

    def _open(self) -> bool:
        entry = self.entries[self.cursor]
        if not entry.is_dir:
            self.chosen = entry.path
            return False
        self._load(entry.path, keep=self.directory.name if entry.is_parent else "")
        return True

    # ---- drawing ------------------------------------------------------------

    def draw(self) -> Rect:
        footer = DIRECTORY_KEYS if self.want is Want.DIRECTORY else FILE_KEYS
        inner = self.paint.frame(letterspace("BROWSE"), "", footer)
        if inner.height < 4:
            return inner
        panes = layout.split(inner, min_list=22, max_list=48)
        if self.entries:
            self.paint.rows(panes.items, [entry.name for entry in self.entries], self.cursor)
        else:
            self.paint.text(panes.items.top, panes.items.left, "Nothing here.", panes.items.width, "label")
        if panes.split and panes.detail and panes.divider_x is not None:
            self.paint.divider(panes.divider_x, inner.top, inner.height - 1)
            self._draw_detail(panes.detail)
        # The directory being listed is the context for every row, so it goes
        # where a message would and a message is not what this screen produces.
        self.paint.text(
            inner.bottom,
            inner.left + 1,
            shorten_path(str(self.directory), inner.width - 2, self.paint.glyph("ellipsis")),
            inner.width - 2,
            "linux",
        )
        return inner

    def _draw_detail(self, area: Rect) -> None:
        if not self.entries:
            return
        entry = self.entries[self.cursor]
        self.paint.text(area.top, area.left, fit(entry.name, area.width), area.width, "text", bold=True)
        self.paint.text(
            area.top + 2,
            area.left,
            shorten_path(str(entry.path), area.width, self.paint.glyph("ellipsis")),
            area.width,
            "linux" if entry.is_dir else "windows",
        )
        if not entry.is_dir:
            self.paint.text(area.top + 4, area.left, human_size(entry.size), area.width, "label")

    # ---- keys ---------------------------------------------------------------

    def handle(self, key: int) -> bool:
        if keys.is_leave(key):
            return False
        if keys.is_left(key) or key in BACK_KEYS:
            self._up()
        elif key == PICK_DIRECTORY and self.want is Want.DIRECTORY:
            self.chosen = self.directory
            return False
        elif not self.entries:
            return True
        elif keys.is_down(key):
            self.cursor = (self.cursor + 1) % len(self.entries)
        elif keys.is_up(key):
            self.cursor = (self.cursor - 1) % len(self.entries)
        elif keys.is_confirm(key):
            return self._open()
        return True

    def choose(self) -> Path | None:
        """Run the screen and return the picked path, or None when cancelled."""
        self.run()
        return self.chosen
