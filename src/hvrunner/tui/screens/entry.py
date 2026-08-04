"""Editing one library entry.

Opening this on a scanned game builds a draft rather than writing one, so
opening the screen and leaving it again is not a silent promotion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...entries import draft, find, remove, update
from ...models import Game
from .. import keys, layout
from ..text import fit, letterspace, shorten_path, wrap
from ..widgets import Rect
from .base import Screen
from .entry_fields import build

if TYPE_CHECKING:
    from ..app import App

KEYS = "j k move   enter change   d delete   esc back"


class EntryScreen(Screen):
    def __init__(self, app: App, game: Game):
        super().__init__(app)
        self.game = game
        self.original_executable = game.executable
        stored = find(app.config, game.executable)
        self.stored = stored is not None
        # A copy, so nothing is written until a field actually changes.
        self.entry = dict(stored) if stored is not None else draft(game)
        self.cursor = 0
        self.dirty = False
        self.fields = build(self)

    def set_field(self, key: str, value: object) -> None:
        if self.entry.get(key) == value:
            return
        self.entry[key] = value
        self.dirty = True

    def draw(self) -> Rect:
        subtitle = "custom entry" if self.stored else "scanned, not yet saved"
        inner = self.paint.frame(letterspace("ENTRY"), subtitle, KEYS)
        if inner.height < 4:
            return inner
        panes = layout.split(inner, min_list=22, max_list=34)
        self.paint.rows(panes.items, [field.label for field in self.fields], self.cursor)
        if panes.split and panes.detail and panes.divider_x is not None:
            self.paint.divider(panes.divider_x, inner.top, inner.height - 1)
            self._draw_detail(panes.detail)
        self.paint.status(inner, self.app.status)
        return inner

    def _draw_detail(self, area: Rect) -> None:
        chosen = self.fields[self.cursor]
        self.paint.text(area.top, area.left, fit(chosen.label, area.width), area.width, "text", bold=True)
        self.paint.text(
            area.top + 2,
            area.left,
            shorten_path(chosen.value(), area.width, self.paint.glyph("ellipsis")),
            area.width,
            "text",
        )
        self.paint.section(area.top + 4, area.left, area.width, "about")
        for offset, line in enumerate(wrap(chosen.detail, area.width)):
            if area.top + 5 + offset > area.bottom:
                break
            self.paint.text(area.top + 5 + offset, area.left, line, area.width, "label")

    def _delete(self) -> None:
        if not self.stored:
            self.app.status = "Nothing to delete: this game comes from the folder scan"
            return
        remove(self.app.config, self.original_executable)
        self.app.save()
        self.app.rescan()
        self.app.status = f"Removed {self.game.name}"

    def _commit(self) -> None:
        if not self.dirty:
            return
        update(self.app.config, self.original_executable, self.entry)
        self.app.save()
        self.app.rescan()
        self.app.status = f"Saved {self.entry.get('name', self.game.name)}"

    def handle(self, key: int) -> bool:
        if keys.is_leave(key):
            self._commit()
            return False
        if keys.is_down(key):
            self.cursor = (self.cursor + 1) % len(self.fields)
        elif keys.is_up(key):
            self.cursor = (self.cursor - 1) % len(self.fields)
        elif keys.is_confirm(key):
            self.fields[self.cursor].activate()
        elif key == ord("d"):
            self._delete()
            return False
        return True
