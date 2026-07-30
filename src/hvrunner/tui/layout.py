"""Splitting an area into a list and a detail pane.

The library and the settings screen share this arrangement, and both must drop
the detail pane at the same width or the two screens disagree about how narrow
is too narrow.
"""

from __future__ import annotations

from dataclasses import dataclass

from .widgets import Rect

# Below this the detail pane cannot hold a readable line, so it is dropped.
TWO_PANE_MINIMUM = 74


@dataclass(frozen=True)
class Panes:
    items: Rect
    detail: Rect | None
    divider_x: int | None

    @property
    def split(self) -> bool:
        return self.detail is not None


def split(inner: Rect, *, min_list: int = 24, max_list: int = 38, reserve_rows: int = 2) -> Panes:
    """Divide inner into a list pane and, when there is room, a detail pane.

    reserve_rows keeps the bottom rows free for the status line.
    """
    top = inner.top + 1
    height = max(1, inner.height - reserve_rows)
    left = inner.left + 1

    if inner.width < TWO_PANE_MINIMUM:
        return Panes(items=Rect(top, left, height, max(1, inner.width - 2)), detail=None, divider_x=None)

    list_width = min(max_list, max(min_list, inner.width // 3))
    divider_x = left + list_width
    detail_width = inner.right - divider_x - 2
    if detail_width < 12:
        return Panes(items=Rect(top, left, height, max(1, inner.width - 2)), detail=None, divider_x=None)
    return Panes(
        items=Rect(top, left, height, list_width),
        detail=Rect(top, divider_x + 2, height, detail_width),
        divider_x=divider_x,
    )
