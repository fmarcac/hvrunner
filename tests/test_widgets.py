from __future__ import annotations

from hvrunner.tui.widgets import Rect


def test_rect_edges():
    rect = Rect(top=1, left=2, height=5, width=10)
    assert rect.bottom == 5
    assert rect.right == 11


def test_single_cell_rect():
    rect = Rect(top=0, left=0, height=1, width=1)
    assert rect.bottom == 0
    assert rect.right == 0


def test_empty_rect_edges_go_negative():
    """A zero sized rect reports edges before its origin, which callers clamp."""
    rect = Rect(top=3, left=4, height=0, width=0)
    assert rect.bottom == 2
    assert rect.right == 3
