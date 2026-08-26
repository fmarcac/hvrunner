"""File browser for a path prompt.

The prompt does not open this itself. Screens do not import one another and the
prompt is not a screen, so app is where the two meet: it runs the prompt, sees
that the browser was asked for, runs this, and feeds the result back.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...core.browsing import Want, human_size, listing
from .. import keys
from ..text import shorten_path
from ..widgets import Rect
from .base import ListDetailScreen

if TYPE_CHECKING:
    from ..app import App

PICK_DIRECTORY = ord("s")

FILE_KEYS = "j k move   enter open or pick   h backspace up   esc cancel"
DIRECTORY_KEYS = "j k move   enter open   h backspace up   s use this folder   esc cancel"


class BrowseScreen(ListDetailScreen):
    title = "BROWSE"
    max_list = 48

    def __init__(self, app: App, directory: Path, want: Want):
        super().__init__(app)
        self.want = want
        self.chosen: Path | None = None
        self.directory = directory
        self.entries = listing(directory, want)

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

    # ---- screen -------------------------------------------------------------

    def labels(self) -> list[str]:
        return [entry.name for entry in self.entries]

    def footer_text(self) -> str:
        return DIRECTORY_KEYS if self.want is Want.DIRECTORY else FILE_KEYS

    def draw_detail(self, area: Rect) -> None:
        if not self.entries:
            return
        entry = self.entries[self.cursor]
        self.paint.detail(area, entry.name, str(entry.path), "linux" if entry.is_dir else "windows")
        if not entry.is_dir:
            self.paint.text(area.top + 4, area.left, human_size(entry.size), area.width, "label")

    def draw_status(self, inner: Rect) -> None:
        # The directory being listed is the context for every row, so it goes
        # where a message would and a message is not what this screen produces.
        self.paint.text(
            inner.bottom,
            inner.left + 1,
            shorten_path(str(self.directory), inner.width - 2, self.paint.glyph("ellipsis")),
            inner.width - 2,
            "linux",
        )

    def confirm(self) -> bool:
        entry = self.entries[self.cursor]
        if not entry.is_dir:
            self.chosen = entry.path
            return False
        self._load(entry.path, keep=self.directory.name if entry.is_parent else "")
        return True

    def extra(self, key: int) -> bool | None:
        if keys.is_back(key):
            self._up()
            return True
        if key == PICK_DIRECTORY and self.want is Want.DIRECTORY:
            self.chosen = self.directory
            return False
        if not self.entries:
            # Nothing to move onto or open, so swallow the rest.
            return True
        return None

    def choose(self) -> Path | None:
        """Run the screen and return the picked path, or None when cancelled."""
        self.run()
        return self.chosen
