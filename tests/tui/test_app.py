from __future__ import annotations

import pytest

from hvrunner.core.constants import SPACEWAR_APPID
from hvrunner.core.models import Game, HvrunnerError


@pytest.fixture
def bare_app():
    """An App with only the state run_game touches.

    Built without __init__ on purpose: that one calls curses, and none of what
    it sets up is involved in deciding what a launch is handed.
    """
    import hvrunner.tui.app as app_module

    app = object.__new__(app_module.App)
    app.games = [Game("G", "Custom", "/tmp/g", "/tmp/g/G.exe", steam_appid="1234")]
    app.selected = 0
    app.config = {}
    app.status = ""
    return app


def _capture(monkeypatch):
    captured: dict[str, Game] = {}

    def fake_launch(game, config):
        captured["game"] = game
        raise HvrunnerError("stopped before starting anything")

    import hvrunner.tui.app as app_module

    monkeypatch.setattr(app_module, "launch", fake_launch)
    return captured


def test_spacewar_overrides_a_declared_id(bare_app, monkeypatch):
    """S exists for the entry declaring an application the user does not own."""
    captured = _capture(monkeypatch)
    bare_app.run_game(as_spacewar=True)
    assert captured["game"].steam_appid == SPACEWAR_APPID


def test_an_ordinary_launch_keeps_the_declared_id(bare_app, monkeypatch):
    captured = _capture(monkeypatch)
    bare_app.run_game()
    assert captured["game"].steam_appid == "1234"


def test_the_override_is_not_persisted(bare_app, monkeypatch):
    """A one off: the replace must never reach the library or the config."""
    _capture(monkeypatch)
    bare_app.run_game(as_spacewar=True)
    assert bare_app.games[0].steam_appid == "1234"
    assert bare_app.config == {}
