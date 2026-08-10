from __future__ import annotations

from hvrunner.core import entries
from hvrunner.core.models import favorite_key


def test_draft_describes_a_scanned_game(game_factory):
    game = game_factory("ACBlackFlag.exe", "BFResynced")
    assert entries.draft(game) == {
        "name": "BFResynced",
        "executable": game.executable,
        "install_dir": game.install_dir,
        "steam_appid": "",
        "launch_args": [],
    }


def test_add_then_find(config, game_factory):
    game = game_factory()
    entries.add(config, entries.draft(game))
    assert entries.find(config, game.executable)["name"] == game.name


def test_update_replaces_in_place(config, game_factory):
    game = game_factory()
    entries.add(config, entries.draft(game))
    changed = {**entries.draft(game), "name": "Renamed"}
    entries.update(config, game.executable, changed)
    assert len(config["custom_games"]) == 1
    assert config["custom_games"][0]["name"] == "Renamed"


def test_update_adds_when_absent(config, game_factory):
    """Promotion: a scanned game has no stored entry to replace."""
    game = game_factory()
    entries.update(config, game.executable, entries.draft(game))
    assert len(config["custom_games"]) == 1


def test_changing_the_executable_moves_the_favourite(config, game_factory):
    """Game.key derives from the executable, so the old key stops matching."""
    game = game_factory("ACBlackFlag.exe", "BFResynced")
    entries.add(config, entries.draft(game))
    config["favorites"] = [favorite_key(game.executable)]
    moved = game.executable.replace("ACBlackFlag.exe", "ACBlackFlag_Plus.exe")
    entries.update(config, game.executable, {**entries.draft(game), "executable": moved})
    assert config["favorites"] == [favorite_key(moved)]


def test_unchanged_executable_leaves_the_favourite_alone(config, game_factory):
    game = game_factory()
    entries.add(config, entries.draft(game))
    config["favorites"] = [favorite_key(game.executable)]
    entries.update(config, game.executable, {**entries.draft(game), "name": "Renamed"})
    assert config["favorites"] == [favorite_key(game.executable)]


def test_remove_drops_the_entry_and_its_favourite(config, game_factory):
    game = game_factory()
    entries.add(config, entries.draft(game))
    config["favorites"] = [favorite_key(game.executable)]
    assert entries.remove(config, game.executable) is True
    assert config["custom_games"] == []
    assert config["favorites"] == []


def test_remove_reports_when_there_was_nothing(config):
    assert entries.remove(config, "/nowhere/absent.exe") is False
