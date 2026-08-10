from __future__ import annotations

from hvrunner.tui.text import fit, letterspace, shorten_path, wrap


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
    assert letterspace("") == ""


def test_wrap_breaks_on_words():
    assert wrap("one two three four", 9) == ["one two", "three", "four"]


def test_wrap_collapses_whitespace():
    assert wrap("  one   two  ", 20) == ["one two"]


def test_wrap_keeps_an_overlong_word_on_its_own_line():
    """Clipping is the drawing layer's job, not the wrapper's."""
    assert wrap("short verylongunbreakableword", 8) == ["short", "verylongunbreakableword"]


def test_wrap_handles_no_room():
    assert wrap("anything", 0) == []
    assert wrap("anything", -3) == []


def test_wrap_of_empty_text():
    assert wrap("", 10) == []


def test_wrap_exact_fit_does_not_break():
    assert wrap("abcd efgh", 9) == ["abcd efgh"]
