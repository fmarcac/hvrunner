from __future__ import annotations

from hvrunner.core.constants import CUSTOM_SOURCE
from hvrunner.core.models import Game, favorite_key


def test_favorite_key_matches_game_key():
    executable = "/games/BFResynced/ACBlackFlag.exe"
    game = Game("Anything", CUSTOM_SOURCE, "/games/BFResynced", executable)
    assert favorite_key(executable) == game.key


def test_key_ignores_the_steam_app_id():
    """Two games sharing an id must not share a favourite key.

    key read appid first once. Had anything ever populated it, every game
    launched as Spacewar would have collided on "Custom:480" and a favourite
    would have followed whichever one was scanned first.
    """
    one = Game("One", "Custom", "/a", "/a/one.exe", steam_appid="480")
    two = Game("Two", "Custom", "/b", "/b/two.exe", steam_appid="480")
    assert one.key == "Custom:/a/one.exe"
    assert two.key == "Custom:/b/two.exe"
    assert one.key != two.key


def test_key_falls_back_to_the_install_dir():
    assert Game("n", "Custom", "/dir", executable="/dir/g.exe").key == "Custom:/dir/g.exe"
    assert Game("n", "Custom", "/dir").key == "Custom:/dir"


def test_slug_is_filesystem_safe():
    assert Game("Assassin's Creed: Black Flag", "Custom", "/d").slug == "assassin-s-creed-black-flag"
    assert Game("   ", "Custom", "/d").slug == "game"
