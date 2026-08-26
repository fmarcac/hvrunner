"""Log feed.

Output already known to be harmless is dimmed rather than hidden, so a real
failure is visible without losing the surrounding context.
"""

from __future__ import annotations

from pathlib import Path

from ...core.logs import LogReader, recent_logs
from .. import keys
from ..text import fit
from ..widgets import Rect
from .base import Screen

KEYS = "j k scroll   pgup pgdn page   g G ends   f follow   n p switch log   esc back"

# Classification to colour role and emphasis.
ROLES: dict[str, tuple[str, dict[str, bool]]] = {
    "command": ("linux", {"bold": True}),
    "noise": ("rule", {}),
    "error": ("error", {}),
    "warning": ("warn", {}),
    "plain": ("text", {}),
}


class LogScreen(Screen):
    poll_interval = 400

    def __init__(self, app):
        super().__init__(app)
        self.available: list[Path] = recent_logs()
        if app.active_log and app.active_log not in self.available:
            self.available.insert(0, app.active_log)
        self.index = self.available.index(app.active_log) if app.active_log in self.available else 0
        self.reader = LogReader(self.available[self.index])
        self.offset = 0
        self.follow = True
        # Set from the interior the frame reports, so paging matches the screen.
        self.rows = 1

    @property
    def lines(self) -> list[str]:
        return self.reader.lines

    def refresh_data(self) -> None:
        self.reader.poll()

    def draw(self) -> Rect:
        dot = self.paint.glyph("dot")
        total = len(self.available)
        meta = f"{len(self.lines)} lines {dot} {'following' if self.follow else 'paused'}"
        if total > 1:
            meta = f"{self.index + 1}/{total} {dot} {meta}"
        inner = self.paint.frame(self.available[self.index].name, meta, KEYS)
        if inner.height < 1:
            return inner

        self.rows = max(1, inner.height)
        if self.follow:
            self.offset = max(0, len(self.lines) - self.rows)

        gutter = len(str(max(1, len(self.lines)))) + 1
        text_left = inner.left + gutter + 1
        text_width = max(0, inner.right - text_left)

        window = slice(self.offset, self.offset + self.rows)
        visible = self.lines[window]
        # Classified once, when the line was read. It never changes afterwards
        # and this redraws several times a second while a game is running.
        kinds = self.reader.kinds[window]
        if not visible:
            self.paint.text(inner.top, text_left, "Waiting for output.", text_width, "label")
        for offset, line in enumerate(visible):
            row = inner.top + offset
            self.paint.text(row, inner.left, str(self.offset + offset + 1).rjust(gutter), gutter, "rule")
            role, emphasis = ROLES[kinds[offset]]
            self.paint.text(row, text_left, fit(line, text_width), text_width, role, **emphasis)
        return inner

    def handle(self, key: int) -> bool:
        if keys.is_leave(key):
            return False
        last = max(0, len(self.lines) - 1)
        if keys.is_down(key):
            self.offset, self.follow = min(self.offset + 1, last), False
        elif keys.is_up(key):
            self.offset, self.follow = max(0, self.offset - 1), False
        elif keys.is_page_down(key):
            self.offset, self.follow = min(self.offset + self.rows, last), False
        elif keys.is_page_up(key):
            self.offset, self.follow = max(0, self.offset - self.rows), False
        elif key == ord("g"):
            self.offset, self.follow = 0, False
        elif key == ord("G"):
            self.follow = True
        elif key == ord("f"):
            self.follow = not self.follow
        elif key in (ord("n"), ord("p")):
            self._switch(-1 if key == ord("n") else 1)
        return True

    def _switch(self, step: int) -> None:
        moved = min(max(self.index + step, 0), len(self.available) - 1)
        if moved == self.index:
            return
        self.index = moved
        self.reader = LogReader(self.available[self.index])
        self.offset, self.follow = 0, True
