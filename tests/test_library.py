from __future__ import annotations

from pathlib import Path

from hvrunner.library import custom_games, display_name, executable_candidates, library, select_executable


def test_display_name_preserves_internal_capitals():
    assert display_name(Path("BFResynced")) == "BFResynced"
    assert display_name(Path("ACBlackFlag")) == "ACBlackFlag"


def test_display_name_capitalises_lowercase_words():
    assert display_name(Path("my-game_v2")) == "My Game V2"
    assert display_name(Path("assassins-creed")) == "Assassins Creed"


def test_display_name_leaves_shouty_names_alone():
    assert display_name(Path("ELDEN RING")) == "ELDEN RING"


def test_display_name_falls_back_to_raw(tmp_path):
    folder = tmp_path / "___"
    folder.mkdir()
    assert display_name(folder) == "___"


def test_prefers_folder_matching_executable(tmp_path):
    folder = tmp_path / "BFResynced"
    folder.mkdir()
    (folder / "AAALauncher.exe").write_bytes(b"x" * 10)
    (folder / "BFResynced.exe").write_bytes(b"x")
    assert select_executable(folder).name == "BFResynced.exe"


def test_size_is_not_a_tiebreak(tmp_path):
    """A larger _Plus sibling must not displace the base binary."""
    folder = tmp_path / "BFResynced"
    folder.mkdir()
    (folder / "ACBlackFlag.exe").write_bytes(b"x" * 100)
    (folder / "ACBlackFlag_Plus.exe").write_bytes(b"x" * 9000)
    assert select_executable(folder).name == "ACBlackFlag.exe"


def test_finds_nested_executable(tmp_path):
    folder = tmp_path / "UEGame"
    (folder / "Binaries" / "Win64").mkdir(parents=True)
    (folder / "Binaries" / "Win64" / "UEGame-Win64-Shipping.exe").write_text("x")
    assert select_executable(folder).name == "UEGame-Win64-Shipping.exe"


def test_prefers_shallower_executable(tmp_path):
    folder = tmp_path / "Game"
    (folder / "sub").mkdir(parents=True)
    (folder / "Top.exe").write_text("x")
    (folder / "sub" / "Game.exe").write_text("x")
    assert select_executable(folder).name == "Top.exe"


def test_ignores_hidden_proton_prefix(tmp_path):
    folder = tmp_path / "WithPrefix"
    hidden = folder / ".hvrunner-proton" / "drive_c" / "windows"
    hidden.mkdir(parents=True)
    (hidden / "explorer.exe").write_bytes(b"x" * 9999)
    (folder / "WithPrefix.exe").write_bytes(b"x")
    assert select_executable(folder).name == "WithPrefix.exe"


def test_filters_installers(tmp_path):
    folder = tmp_path / "Game"
    folder.mkdir()
    (folder / "UnityCrashHandler64.exe").write_text("x")
    (folder / "vcredist_x64.exe").write_text("x")
    (folder / "Game.exe").write_text("x")
    assert select_executable(folder).name == "Game.exe"


def test_installer_only_folder_still_returns_something(tmp_path):
    folder = tmp_path / "Game"
    folder.mkdir()
    (folder / "setup.exe").write_text("x")
    assert select_executable(folder).name == "setup.exe"


def test_no_executables_returns_none(tmp_path):
    folder = tmp_path / "Empty"
    folder.mkdir()
    assert select_executable(folder) is None


def test_depth_limit_is_respected(tmp_path):
    folder = tmp_path / "Deep"
    deep = folder / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    (deep / "TooDeep.exe").write_text("x")
    assert executable_candidates(folder, max_depth=2) == []


def test_duplicate_roots_yield_one_entry(tmp_path, config):
    folder = tmp_path / "OneGame"
    folder.mkdir()
    (folder / "OneGame.exe").write_text("x")
    config["library_roots"] = [str(tmp_path), str(tmp_path)]
    assert len(custom_games(config, set())) == 1


def test_favorite_survives_a_rescan(tmp_path, config):
    folder = tmp_path / "OneGame"
    folder.mkdir()
    (folder / "OneGame.exe").write_text("x")
    first = custom_games(config, set())
    stored = {first[0].key}
    assert custom_games(config, stored)[0].favorite is True


def test_favorites_sort_first(tmp_path, config):
    for name in ("Alpha", "Zulu"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / f"{name}.exe").write_text("x")
    zulu_key = next(g.key for g in custom_games(config, set()) if g.name == "Zulu")
    config["favorites"] = [zulu_key]
    assert [game.name for game in library(config)] == ["Zulu", "Alpha"]


def test_missing_root_is_skipped(config):
    config["library_roots"] = ["/definitely/not/here"]
    assert custom_games(config, set()) == []


def test_declared_game_is_included(tmp_path, config):
    exe = tmp_path / "Solo" / "Solo.exe"
    exe.parent.mkdir()
    exe.write_text("x")
    config["library_roots"] = []
    config["custom_games"] = [{"name": "Solo Game", "executable": str(exe), "launch_args": ["-dx12", 5]}]
    games = custom_games(config, set())
    assert len(games) == 1
    assert games[0].name == "Solo Game"
    # Non string arguments are dropped rather than crashing.
    assert games[0].launch_args == ("-dx12",)


def test_declared_game_does_not_duplicate_a_scanned_one(tmp_path, config):
    folder = tmp_path / "OneGame"
    folder.mkdir()
    exe = folder / "OneGame.exe"
    exe.write_text("x")
    config["custom_games"] = [{"name": "Dup", "executable": str(exe)}]
    assert len(custom_games(config, set())) == 1


def test_malformed_custom_entries_are_skipped(config):
    config["library_roots"] = []
    config["custom_games"] = ["nonsense", {"executable": "/absent.exe"}, {}]
    assert custom_games(config, set()) == []


def test_declared_entry_overrides_the_scanned_folder(tmp_path, config):
    """Repointing a game must replace its scanned row, not sit beside it."""
    folder = tmp_path / "BFResynced"
    folder.mkdir()
    (folder / "ACBlackFlag.exe").write_text("x")
    (folder / "ACBlackFlag_Plus.exe").write_text("x")
    config["custom_games"] = [
        {
            "name": "Black Flag Plus",
            "executable": str(folder / "ACBlackFlag_Plus.exe"),
            "install_dir": str(folder),
        }
    ]
    games = custom_games(config, set())
    assert [game.name for game in games] == ["Black Flag Plus"]
    assert games[0].executable.endswith("ACBlackFlag_Plus.exe")


def test_install_dir_defaults_to_the_executable_parent(tmp_path, config):
    exe = tmp_path / "Solo" / "Solo.exe"
    exe.parent.mkdir()
    exe.write_text("x")
    config["library_roots"] = []
    config["custom_games"] = [{"name": "Solo", "executable": str(exe)}]
    assert custom_games(config, set())[0].install_dir == str(exe.parent)


def test_two_declared_entries_can_share_a_folder(tmp_path, config):
    """A game and its mod loader live together, and both must stay visible."""
    folder = tmp_path / "Skyrim"
    folder.mkdir()
    (folder / "Skyrim.exe").write_text("x")
    (folder / "skse64_loader.exe").write_text("x")
    config["library_roots"] = []
    config["custom_games"] = [
        {"name": "Skyrim", "executable": str(folder / "Skyrim.exe")},
        {"name": "Skyrim SKSE", "executable": str(folder / "skse64_loader.exe")},
    ]
    assert [game.name for game in custom_games(config, set())] == ["Skyrim", "Skyrim SKSE"]


def test_install_dir_is_used_when_given(tmp_path, config):
    """An installed game lives inside its own prefix, so the folder must be explicit."""
    target = tmp_path / "Witcher3"
    exe = target / ".hvrunner-proton" / "pfx" / "drive_c" / "w3.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("x")
    config["library_roots"] = []
    config["custom_games"] = [{"name": "W3", "executable": str(exe), "install_dir": str(target)}]
    assert custom_games(config, set())[0].install_dir == str(target)
