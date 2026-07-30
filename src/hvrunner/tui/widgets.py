"""A themed drawing surface that clips rather than raising.

Every helper takes an explicit width and silently does nothing when there is no
room. curses raises on a negative length and on the last cell of a window, and
neither is worth propagating to the caller.
"""

from __future__ import annotations

import contextlib
import curses
from dataclasses import dataclass
from typing import Any

from .text import fit, shorten_path
from .theme import Theme


@dataclass(frozen=True)
class Rect:
    top: int
    left: int
    height: int
    width: int

    @property
    def bottom(self) -> int:
        return self.top + self.height - 1

    @property
    def right(self) -> int:
        return self.left + self.width - 1


def draw_text(window: Any, y: int, x: int, text: str, width: int, attribute: int = 0) -> None:
    if width <= 0 or y < 0 or x < 0 or not text:
        return
    with contextlib.suppress(curses.error):
        window.addnstr(y, x, text, width, attribute)


class Painter:
    def __init__(self, screen: Any, theme: Theme):
        self.screen = screen
        self.theme = theme

    # ---- basics -------------------------------------------------------------

    @property
    def size(self) -> tuple[int, int]:
        height, width = self.screen.getmaxyx()
        return height, width

    def glyph(self, name: str) -> str:
        return self.theme.glyph(name)

    def attr(self, role: str, **kwargs: bool) -> int:
        return self.theme.attr(role, **kwargs)

    def text(self, y: int, x: int, text: str, width: int, role: str = "text", **kwargs: bool) -> None:
        draw_text(self.screen, y, x, text, width, self.theme.attr(role, **kwargs))

    # ---- structure ----------------------------------------------------------

    def frame(self, title: str, meta: str = "", footer: str = "") -> Rect:
        """Outer border with a title in the top rule and keys in the bottom.

        Returns the usable interior.
        """
        height, width = self.size
        if height < 4 or width < 20:
            return Rect(0, 0, max(0, height), max(0, width))
        horizontal = self.glyph("h")
        rule = self.attr("rule")
        span = width - 2

        self.text(0, 0, self.glyph("tl"), 1, "rule")
        draw_text(self.screen, 0, 1, horizontal * span, span, rule)
        self.text(0, width - 1, self.glyph("tr"), 1, "rule")
        self.text(height - 1, 0, self.glyph("bl"), 1, "rule")
        draw_text(self.screen, height - 1, 1, horizontal * span, span, rule)
        self.text(height - 1, width - 1, self.glyph("br"), 1, "rule")
        for row in range(1, height - 1):
            self.text(row, 0, self.glyph("v"), 1, "rule")
            self.text(row, width - 1, self.glyph("v"), 1, "rule")

        if title:
            self.text(0, 2, f" {title} ", max(0, width - 4), "linux", bold=True)
        if meta:
            label = f" {meta} "
            start = max(2, width - 2 - len(label))
            self.text(0, start, label, max(0, width - start - 1), "label")
        if footer:
            label = f" {footer} "
            self.text(height - 1, 2, fit(label, max(0, width - 4)), max(0, width - 4), "label")

        return Rect(top=1, left=1, height=max(0, height - 2), width=max(0, width - 2))

    def divider(self, x: int, top: int, height: int) -> None:
        vertical = self.glyph("v")
        for row in range(top, top + height):
            self.text(row, x, vertical, 1, "rule")

    def section(self, y: int, x: int, width: int, label: str) -> None:
        """A small caps heading followed by a hairline to the right margin."""
        if width <= 0:
            return
        self.text(y, x, label.upper(), width, "label", bold=True)
        used = len(label) + 1
        remaining = width - used
        if remaining > 1:
            draw_text(self.screen, y, x + used, self.glyph("h") * (remaining - 1), remaining - 1, self.attr("rule"))

    def row(self, y: int, x: int, width: int, text: str, role: str, selected: bool) -> None:
        """A list row, marked by a solid bar when it is the cursor."""
        if width <= 0:
            return
        bar = self.glyph("bar") if selected else " "
        self.text(y, x, bar, 1, "linux", bold=True)
        self.text(y, x + 2, fit(text, width - 2, self.glyph("ellipsis")), width - 2, role, bold=selected)

    def rows(self, area: Rect, labels: list[str], selected: int) -> None:
        """A scrolling list that keeps the cursor near the middle."""
        if area.height <= 0 or not labels:
            return
        start = max(0, min(selected - area.height // 2, len(labels) - area.height))
        for offset, label in enumerate(labels[start : start + area.height]):
            index = start + offset
            chosen = index == selected
            self.row(area.top + offset, area.left, area.width, label, "linux" if chosen else "text", chosen)

    def status(self, inner: Rect, message: str) -> None:
        if not message:
            return
        self.text(
            inner.bottom,
            inner.left + 1,
            fit(message, inner.width - 2, self.glyph("ellipsis")),
            inner.width - 2,
            "warn",
        )

    def field(
        self,
        y: int,
        x: int,
        width: int,
        name: str,
        value: str,
        role: str = "text",
        name_width: int | None = None,
    ) -> None:
        """A label and value pair on one line.

        Pass name_width so a group of fields shares one label column. Computing
        it per row leaves the values ragged.
        """
        if width <= 0:
            return
        column = name_width if name_width is not None else len(name) + 1
        column = min(max(1, column), max(1, width - 4))
        self.text(y, x, fit(name, column), column, "label")
        value_x = x + column + 1
        value_width = width - column - 1
        if value_width > 0:
            self.text(y, value_x, shorten_path(value, value_width, self.glyph("ellipsis")), value_width, role)
