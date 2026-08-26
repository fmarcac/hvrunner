from __future__ import annotations

import pytest

from hvrunner.tui.screens.entry_fields import clean_steam_appid, format_env, parse_env


@pytest.mark.parametrize("value", ["480", " 480 ", "", "   "])
def test_a_valid_id_is_accepted(value):
    assert clean_steam_appid(value) == value.strip()


@pytest.mark.parametrize("value", ["app-480", "48o", "4 80", "-1", "480.0"])
def test_a_value_that_is_not_a_number_is_refused(value):
    """umu would run as application 0 rather than complain about any of these."""
    assert clean_steam_appid(value) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", {}),
        ("   ", {}),
        ("DXVK_HUD=fps", {"DXVK_HUD": "fps"}),
        ("A=1 B=2", {"A": "1", "B": "2"}),
        # An empty value is meaningful: it is how a name is set but blank.
        ("WINEDEBUG=", {"WINEDEBUG": ""}),
    ],
)
def test_environment_pairs_are_parsed(text, expected):
    assert parse_env(text) == expected


@pytest.mark.parametrize("text", ["DXVK_HUD", "=fps", "A=1 B"])
def test_something_that_is_not_a_pair_is_refused(text):
    assert parse_env(text) is None


def test_formatting_round_trips():
    values = {"A": "1", "B": "2"}
    assert parse_env(format_env(values)) == values


def test_formatting_nothing_gives_an_empty_field():
    assert format_env({}) == ""
    assert format_env(None) == ""
    assert format_env("not a mapping") == ""
