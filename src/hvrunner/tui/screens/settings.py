"""Settings screen: layout only. What the settings are lives next door."""

from __future__ import annotations

from ..widgets import Rect
from .base import ListDetailScreen
from .settings_entries import build

KEYS = "j k move   enter change   esc back"


class SettingsScreen(ListDetailScreen):
    title = "SETTINGS"
    footer = KEYS

    def __init__(self, app):
        super().__init__(app)
        self.settings = build(app)

    def labels(self) -> list[str]:
        return [setting.label for setting in self.settings]

    def meta(self) -> str:
        return str(self.app.path)

    def draw_detail(self, area: Rect) -> None:
        chosen = self.settings[self.cursor]
        self.paint.detail(area, chosen.label, chosen.value(), chosen.role(), chosen.detail)

    def confirm(self) -> bool:
        self.settings[self.cursor].activate()
        return True

    def extra(self, key: int) -> bool | None:
        # Space toggles too, because most of these are booleans.
        if key == ord(" "):
            return self.confirm()
        return None
