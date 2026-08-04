"""A single choice list.

Its first caller is the post-install picker, which has to ask which of several
binaries in a fresh prefix is the game.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from .. import keys, layout
from ..text import fit, letterspace, shorten_path
from ..widgets import Rect
from .base import Screen

if TYPE_CHECKING:
    from ..app import App

KEYS = "j k move   enter select   esc skip"


class PickerScreen(Screen):
    def __init__(self, app: App, title: str, subtitle: str, options: Sequence[tuple[str, str]]):
        super().__init__(app)
        self.title = title
        self.subtitle = subtitle
        self.options = list(options)
        self.cursor = 0
        self.chosen: int | None = None

    def draw(self) -> Rect:
        inner = self.paint.frame(letterspace(self.title), self.subtitle, KEYS)
        if inner.height < 4:
            return inner
        panes = layout.split(inner, min_list=22, max_list=40)
        self.paint.rows(panes.items, [label for label, _ in self.options], self.cursor)
        if panes.split and panes.detail and panes.divider_x is not None:
            self.paint.divider(panes.divider_x, inner.top, inner.height - 1)
            self._draw_detail(panes.detail)
        self.paint.status(inner, self.app.status)
        return inner

    def _draw_detail(self, area: Rect) -> None:
        label, detail = self.options[self.cursor]
        self.paint.text(area.top, area.left, fit(label, area.width), area.width, "text", bold=True)
        self.paint.text(
            area.top + 2,
            area.left,
            shorten_path(detail, area.width, self.paint.glyph("ellipsis")),
            area.width,
            "windows",
        )

    def handle(self, key: int) -> bool:
        if keys.is_leave(key):
            return False
        if keys.is_down(key):
            self.cursor = (self.cursor + 1) % len(self.options)
        elif keys.is_up(key):
            self.cursor = (self.cursor - 1) % len(self.options)
        elif keys.is_confirm(key):
            self.chosen = self.cursor
            return False
        return True

    def choose(self) -> int | None:
        """Run the screen and return the chosen index, or None when skipped."""
        if not self.options:
            return None
        self.run()
        return self.chosen
