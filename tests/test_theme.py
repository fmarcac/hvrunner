from __future__ import annotations

from hvrunner.tui import theme as theme_module
from hvrunner.tui.theme import Theme


def test_every_role_has_a_fallback():
    """A terminal with only eight colours must still get a colour per role."""
    assert set(theme_module._ROLES) == set(theme_module._FALLBACK)


def test_palette_uses_fixed_cube_indices():
    """init_color would mutate the terminal's own palette, so it is not used."""
    for index in theme_module._ROLES.values():
        assert isinstance(index, int)
        assert 16 <= index <= 255


def test_glyph_sets_cover_the_same_names():
    assert set(theme_module._UNICODE) == set(theme_module._ASCII)


def test_glyphs_chosen_without_a_terminal():
    chosen = Theme().glyphs
    assert chosen in (theme_module._UNICODE, theme_module._ASCII)


def test_unknown_glyph_does_not_raise():
    assert Theme().glyph("nonexistent") == "?"


def test_monochrome_falls_back_to_emphasis():
    """With no colour pairs, hierarchy comes from bold and dim instead of hue."""
    import curses

    theme = Theme()
    assert theme.colored is False
    assert theme.attr("linux") & curses.A_BOLD
    assert theme.attr("favourite") & curses.A_BOLD
    assert theme.attr("rule") & curses.A_DIM
    assert theme.attr("label") & curses.A_DIM
    assert theme.attr("text") == 0
