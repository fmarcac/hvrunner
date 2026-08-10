"""Library browser."""

from __future__ import annotations

from ...core.constants import APP_NAME
from .. import keys, layout
from ..text import letterspace
from ..widgets import Rect
from . import preview
from .base import Screen

KEYS = "enter run   S spacewar   e edit   a add   i install   r rescan   l logs   s settings   f favourite   ? keys   q quit"


class LibraryScreen(Screen):
    #: Only so a launch that dies can correct its own status line rather than
    #: waiting for the next keypress to notice.
    poll_interval = 500

    def refresh_data(self) -> None:
        self.app.check_launch()

    def draw(self) -> Rect:
        app = self.app
        favourites = sum(1 for game in app.games if game.favorite)
        meta = "1 title" if len(app.games) == 1 else f"{len(app.games)} titles"
        if favourites:
            meta += f" {self.paint.glyph('dot')} {favourites} favourite"

        inner = self.paint.frame(letterspace(APP_NAME.upper()), meta, KEYS)
        # Below this there is no room for even one row after the padding.
        if inner.height < 4:
            return inner

        panes = layout.split(inner)
        if not app.games:
            self._draw_empty(panes.items)
        else:
            star = self.paint.glyph("star")
            labels = [f"{star if game.favorite else ' '} {game.name}" for game in app.games]
            self.paint.rows(panes.items, labels, app.selected)

        if panes.split and panes.divider_x is not None:
            self.paint.divider(panes.divider_x, inner.top, inner.height - 1)
            current = app.current
            if current and panes.detail:
                preview.draw(self.paint, panes.detail, current, app.config)

        self.paint.status(inner, app.status)
        return inner

    def _draw_empty(self, area: Rect) -> None:
        self.paint.text(area.top, area.left, "No games yet.", area.width, "text", bold=True)
        self.paint.text(area.top + 2, area.left, "s  add a library folder", area.width, "label")
        self.paint.text(area.top + 3, area.left, "a  add a single executable", area.width, "label")
        self.paint.text(area.top + 4, area.left, "i  run a Windows installer", area.width, "label")

    def handle(self, key: int) -> bool:
        app = self.app
        if keys.is_leave(key):
            return False
        if keys.is_down(key):
            app.move(1)
        elif keys.is_up(key):
            app.move(-1)
        elif keys.is_confirm(key):
            app.run_game()
        elif key == ord("S"):
            app.run_game(as_spacewar=True)
        elif key == ord("f"):
            app.toggle_favourite()
        elif key == ord("r"):
            app.rescan()
            app.status = "1 title" if len(app.games) == 1 else f"{len(app.games)} titles"
        elif key == ord("a"):
            app.add_executable()
        elif key == ord("e"):
            app.edit_entry()
        elif key == ord("i"):
            app.install_game()
        elif key == ord("l"):
            app.open_logs()
        elif key == ord("s"):
            app.open_settings()
        elif key == ord("?"):
            app.open_help()
        return True
