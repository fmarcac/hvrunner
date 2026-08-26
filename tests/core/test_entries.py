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
        "proton_path": "",
        "launch_args": [],
        "env": {},
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


def test_declare_always_sets_the_install_folder():
    """Left unset, it is inferred as the binary's own folder, a level too deep."""
    entry = entries.declare("Hitman", "/games/Hitman/Hitman Absolution/HMA.exe", "/games/Hitman")
    assert entry == {
        "name": "Hitman",
        "executable": "/games/Hitman/Hitman Absolution/HMA.exe",
        "install_dir": "/games/Hitman",
        "launch_args": [],
    }


def test_declare_accepts_paths(tmp_path):
    entry = entries.declare("G", tmp_path / "G.exe", tmp_path)
    assert entry["executable"] == str(tmp_path / "G.exe")
    assert entry["install_dir"] == str(tmp_path)


def test_a_declared_entry_reaches_the_library_with_its_folder(config, tmp_path):
    from hvrunner.core.library import library

    folder = tmp_path / "Hitman"
    executable = folder / "Hitman Absolution" / "HMA.exe"
    executable.parent.mkdir(parents=True)
    executable.write_text("stub")
    entries.add(config, entries.declare("Hitman", executable, folder))
    game = next(item for item in library(config) if item.name == "Hitman")
    assert game.install_dir == str(folder)


def test_an_entry_carries_its_environment_into_the_game(config, tmp_path):
    from hvrunner.core.library import library

    executable = tmp_path / "G" / "G.exe"
    executable.parent.mkdir(parents=True)
    executable.write_text("stub")
    entry = entries.declare("G", executable, executable.parent)
    entry["env"] = {"DXVK_HUD": "fps"}
    entries.add(config, entry)
    game = next(item for item in library(config) if item.name == "G")
    assert game.env == (("DXVK_HUD", "fps"),)


def test_a_malformed_environment_is_ignored_rather_than_fatal(config, tmp_path):
    from hvrunner.core.library import library

    executable = tmp_path / "G" / "G.exe"
    executable.parent.mkdir(parents=True)
    executable.write_text("stub")
    entry = entries.declare("G", executable, executable.parent)
    entry["env"] = "DXVK_HUD=fps"
    entries.add(config, entry)
    assert next(item for item in library(config) if item.name == "G").env == ()
