from __future__ import annotations

import pytest

from hvrunner.tui.editline import EditLine, scroll_offset

LONG_PATH = "/mnt/data/games/Hitman-Absolution-AnkerGames/Hitman Absolution/HMA.exe"


def test_starts_at_the_end_of_the_initial_value():
    line = EditLine("/mnt/data")
    assert line.cursor == len(line.text)


def test_nothing_caps_the_length():
    """getstr capped input at the width of the field, which truncated real paths."""
    line = EditLine()
    for character in LONG_PATH:
        line.insert(character)
    assert line.text == LONG_PATH


def test_backspace_removes_rather_than_inserting():
    line = EditLine("games")
    line.backspace()
    assert line.text == "game"
    assert line.cursor == 4


def test_backspace_at_the_start_is_a_no_op():
    line = EditLine("games")
    line.to_start()
    line.backspace()
    assert line.text == "games"
    assert line.cursor == 0


def test_insert_and_delete_happen_at_the_cursor():
    line = EditLine("gams")
    line.move(-1)
    line.insert("e")
    assert line.text == "games"
    line.to_start()
    line.delete()
    assert line.text == "ames"


def test_delete_at_the_end_is_a_no_op():
    line = EditLine("games")
    line.delete()
    assert line.text == "games"


def test_move_clamps_at_both_ends():
    line = EditLine("ab")
    line.move(-99)
    assert line.cursor == 0
    line.move(99)
    assert line.cursor == 2


def test_kill_word_walks_up_one_directory():
    line = EditLine("/mnt/data/games/Hitman")
    line.kill_word()
    assert line.text == "/mnt/data/games/"


def test_kill_word_ignores_a_trailing_separator():
    """Otherwise the cursor sits just past a slash and nothing at all is removed."""
    line = EditLine("/mnt/data/games/")
    line.kill_word()
    assert line.text == "/mnt/data/"


def test_kill_to_start_keeps_the_tail():
    line = EditLine("/mnt/data")
    line.move(-4)
    line.kill_to_start()
    assert line.text == "data"
    assert line.cursor == 0


@pytest.mark.parametrize("width", [1, 5, 40])
def test_scroll_offset_always_keeps_the_cursor_visible(width):
    offset = 0
    for cursor in [*range(len(LONG_PATH) + 1), *range(len(LONG_PATH), -1, -1)]:
        offset = scroll_offset(cursor, width, offset)
        assert offset <= cursor <= offset + width - 1
        assert offset >= 0


def test_scroll_offset_holds_still_while_the_cursor_is_in_view():
    assert scroll_offset(5, 10, 3) == 3


def test_scroll_offset_survives_a_field_with_no_room():
    assert scroll_offset(9, 0, 4) == 0
