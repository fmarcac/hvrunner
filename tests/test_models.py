from __future__ import annotations

from hvrunner.constants import CUSTOM_SOURCE
from hvrunner.models import Game, favorite_key


def test_favorite_key_matches_game_key():
    executable = "/games/BFResynced/ACBlackFlag.exe"
    game = Game("Anything", CUSTOM_SOURCE, "/games/BFResynced", executable)
    assert favorite_key(executable) == game.key


def test_key_falls_back_through_appid_then_executable():
    assert Game("n", "Custom", "/dir", appid="42").key == "Custom:42"
    assert Game("n", "Custom", "/dir", executable="/dir/g.exe").key == "Custom:/dir/g.exe"
    assert Game("n", "Custom", "/dir").key == "Custom:/dir"


def test_slug_is_filesystem_safe():
    assert Game("Assassin's Creed: Black Flag", "Custom", "/d").slug == "assassin-s-creed-black-flag"
    assert Game("   ", "Custom", "/d").slug == "game"
