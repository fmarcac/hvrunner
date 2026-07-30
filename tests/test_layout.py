from __future__ import annotations

from hvrunner.tui.layout import TWO_PANE_MINIMUM, split
from hvrunner.tui.widgets import Rect


def wide(width: int = 100, height: int = 24) -> Rect:
    return Rect(top=1, left=1, height=height, width=width)


def test_wide_area_splits():
    panes = split(wide())
    assert panes.split
    assert panes.detail is not None
    assert panes.divider_x is not None


def test_narrow_area_does_not_split():
    panes = split(wide(width=TWO_PANE_MINIMUM - 1))
    assert not panes.split
    assert panes.detail is None
    assert panes.divider_x is None


def test_panes_do_not_overlap():
    panes = split(wide())
    assert panes.divider_x is not None
    assert panes.items.right < panes.divider_x
    assert panes.detail is not None
    assert panes.detail.left > panes.divider_x


def test_detail_stays_inside_the_area():
    area = wide()
    panes = split(area)
    assert panes.detail is not None
    assert panes.detail.right <= area.right


def test_list_width_is_bounded():
    panes = split(wide(width=400))
    assert panes.items.width <= 38
    panes = split(wide(width=TWO_PANE_MINIMUM))
    assert panes.items.width >= 24


def test_rows_are_reserved_for_the_status_line():
    area = wide(height=24)
    panes = split(area, reserve_rows=2)
    assert panes.items.bottom < area.bottom


def test_tiny_area_still_returns_a_usable_rect():
    panes = split(Rect(top=1, left=1, height=1, width=4))
    assert panes.items.width >= 1
    assert panes.items.height >= 1
