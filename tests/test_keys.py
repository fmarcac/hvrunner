from __future__ import annotations

import curses

from hvrunner.tui import keys


def test_down_accepts_arrow_and_vi():
    assert keys.is_down(curses.KEY_DOWN)
    assert keys.is_down(ord("j"))
    assert not keys.is_down(ord("k"))


def test_up_accepts_arrow_and_vi():
    assert keys.is_up(curses.KEY_UP)
    assert keys.is_up(ord("k"))
    assert not keys.is_up(ord("j"))


def test_confirm_accepts_both_returns():
    assert keys.is_confirm(10)
    assert keys.is_confirm(13)
    assert keys.is_confirm(curses.KEY_ENTER)
    assert not keys.is_confirm(ord(" "))


def test_leave_accepts_escape_and_q():
    assert keys.is_leave(keys.ESCAPE)
    assert keys.is_leave(ord("q"))
    assert not keys.is_leave(ord("Q"))


def test_paging():
    assert keys.is_page_down(curses.KEY_NPAGE)
    assert keys.is_page_up(curses.KEY_PPAGE)
    assert not keys.is_page_down(curses.KEY_PPAGE)


def test_no_binding_is_claimed_twice():
    """A key must not mean two things on the same screen."""
    probes = [curses.KEY_DOWN, curses.KEY_UP, ord("j"), ord("k"), 10, 13, ord("q"), keys.ESCAPE]
    checks = (keys.is_down, keys.is_up, keys.is_confirm, keys.is_leave, keys.is_page_down, keys.is_page_up)
    for probe in probes:
        assert sum(1 for check in checks if check(probe)) <= 1, probe
