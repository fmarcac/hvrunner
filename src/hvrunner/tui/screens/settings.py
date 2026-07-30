"""Settings screen."""

from __future__ import annotations

from .. import keys, layout
from ..text import fit, letterspace, shorten_path, wrap
from ..widgets import Rect
from .base import Screen
from .settings_entries import build

KEYS = "j k move   enter change   esc back"


class SettingsScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.cursor = 0
        self.settings = build(app)

    def draw(self) -> Rect:
        inner = self.paint.frame(letterspace("SETTINGS"), str(self.app.path), KEYS)
        if inner.height < 4:
            return inner

        panes = layout.split(inner, min_list=22, max_list=34)
        self.paint.rows(panes.items, [setting.label for setting in self.settings], self.cursor)

        if panes.split and panes.detail and panes.divider_x is not None:
            self.paint.divider(panes.divider_x, inner.top, inner.height - 1)
            self._draw_detail(panes.detail)

        self.paint.status(inner, self.app.status)
        return inner

    def _draw_detail(self, area: Rect) -> None:
        chosen = self.settings[self.cursor]
        self.paint.text(area.top, area.left, fit(chosen.label, area.width), area.width, "text", bold=True)
        self.paint.text(
            area.top + 2,
            area.left,
            shorten_path(chosen.value(), area.width, self.paint.glyph("ellipsis")),
            area.width,
            chosen.role(),
        )
        self.paint.section(area.top + 4, area.left, area.width, "about")
        for offset, line in enumerate(wrap(chosen.detail, area.width)):
            if area.top + 5 + offset > area.bottom:
                break
            self.paint.text(area.top + 5 + offset, area.left, line, area.width, "label")

    def handle(self, key: int) -> bool:
        if keys.is_leave(key):
            return False
        if keys.is_down(key):
            self.cursor = (self.cursor + 1) % len(self.settings)
        elif keys.is_up(key):
            self.cursor = (self.cursor - 1) % len(self.settings)
        elif keys.is_confirm(key) or key == ord(" "):
            self.settings[self.cursor].activate()
        return True
