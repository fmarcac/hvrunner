"""Editing one library entry.

Opening this on a scanned game builds a draft rather than writing one, so
opening the screen and leaving it again is not a silent promotion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.entries import draft, find, remove, update
from ...core.models import Game
from ..widgets import Rect
from .base import ListDetailScreen
from .entry_fields import build

if TYPE_CHECKING:
    from ..app import App

KEYS = "j k move   enter change   d delete   esc back"


class EntryScreen(ListDetailScreen):
    title = "ENTRY"
    footer = KEYS

    def __init__(self, app: App, game: Game):
        super().__init__(app)
        self.game = game
        self.original_executable = game.executable
        stored = find(app.config, game.executable)
        self.stored = stored is not None
        # A copy, so nothing is written until a field actually changes.
        self.entry = dict(stored) if stored is not None else draft(game)
        self.dirty = False
        self.fields = build(self)

    def set_field(self, key: str, value: object) -> None:
        if self.entry.get(key) == value:
            return
        self.entry[key] = value
        self.dirty = True

    def labels(self) -> list[str]:
        return [field.label for field in self.fields]

    def meta(self) -> str:
        return "custom entry" if self.stored else "scanned, not yet saved"

    def draw_detail(self, area: Rect) -> None:
        chosen = self.fields[self.cursor]
        self.paint.detail(area, chosen.label, chosen.value(), chosen.role(), chosen.detail)

    def confirm(self) -> bool:
        self.fields[self.cursor].activate()
        return True

    def leave(self) -> bool:
        self._commit()
        return False

    def extra(self, key: int) -> bool | None:
        if key == ord("d"):
            # Staying put on a refusal keeps any pending edits, and puts the
            # explanation on the screen the user is actually looking at.
            return not self._delete()
        return None

    def _delete(self) -> bool:
        """True when the entry went away, which is when the screen should close."""
        if not self.stored:
            self.app.status = "Nothing to delete: this game comes from the folder scan"
            return False
        remove(self.app.config, self.original_executable)
        self.app.save()
        self.app.rescan()
        self.app.status = f"Removed {self.game.name}"
        return True

    def _commit(self) -> None:
        if not self.dirty:
            return
        update(self.app.config, self.original_executable, self.entry)
        self.app.save()
        self.app.rescan()
        self.app.status = f"Saved {self.entry.get('name', self.game.name)}"
