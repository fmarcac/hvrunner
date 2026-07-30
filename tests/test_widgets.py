from __future__ import annotations

from hvrunner.tui.widgets import Rect, fit, letterspace, shorten_path


def test_fit_leaves_short_text_alone():
    assert fit("abc", 10) == "abc"
    assert fit("abc", 3) == "abc"


def test_fit_truncates_with_an_ellipsis():
    assert fit("abcdefghij", 6) == "abc..."
    assert fit("abcdefghij", 6, "…") == "abcde…"


def test_fit_handles_no_room():
    assert fit("abcdef", 0) == ""
    assert fit("abcdef", -4) == ""
    assert fit("abcdef", 2) == "ab"


def test_shorten_path_keeps_the_tail():
    shortened = shorten_path("/very/long/path/to/game.exe", 12)
    assert shortened == ".../game.exe"
    assert len(shortened) == 12
    assert shorten_path("/short", 12) == "/short"


def test_shorten_path_handles_no_room():
    assert shorten_path("/a/b/c", 0) == ""
    assert shorten_path("/a/b/c", 2) == "/c"


def test_letterspace():
    assert letterspace("ABC") == "A B C"
    assert letterspace("ABC", 2) == "A  B  C"


def test_rect_edges():
    rect = Rect(top=1, left=2, height=5, width=10)
    assert rect.bottom == 5
    assert rect.right == 11
