from __future__ import annotations

import pytest

from hvrunner.tui.screens.entry_fields import clean_steam_appid


@pytest.mark.parametrize("value", ["480", " 480 ", "", "   "])
def test_a_valid_id_is_accepted(value):
    assert clean_steam_appid(value) == value.strip()


@pytest.mark.parametrize("value", ["umu-480", "48o", "4 80", "-1", "480.0"])
def test_a_value_umu_cannot_parse_is_refused(value):
    """umu would run as application 0 rather than complain about any of these."""
    assert clean_steam_appid(value) is None
