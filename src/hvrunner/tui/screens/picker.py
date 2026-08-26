"""A single choice list.

Its first caller is the post-install picker, which has to ask which of several
binaries in a fresh prefix is the game.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ..widgets import Rect
from .base import ListDetailScreen

if TYPE_CHECKING:
    from ..app import App

KEYS = "j k move   enter select   esc skip"


class PickerScreen(ListDetailScreen):
    footer = KEYS
    max_list = 40

    def __init__(self, app: App, title: str, subtitle: str, options: Sequence[tuple[str, str]]):
        super().__init__(app)
        self.title = title
        self.subtitle = subtitle
        self.options = list(options)
        self.chosen: int | None = None

    def labels(self) -> list[str]:
        return [label for label, _ in self.options]

    def meta(self) -> str:
        return self.subtitle

    def draw_detail(self, area: Rect) -> None:
        label, detail = self.options[self.cursor]
        self.paint.detail(area, label, detail, "windows")

    def confirm(self) -> bool:
        self.chosen = self.cursor
        return False

    def choose(self) -> int | None:
        """Run the screen and return the chosen index, or None when skipped."""
        if not self.options:
            return None
        self.run()
        return self.chosen
