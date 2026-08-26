from __future__ import annotations

from pathlib import Path

from hvrunner.core.library import (
    custom_games,
    display_name,
    executable_candidates,
    game_folder,
    library,
    select_executable,
    sort_games,
)


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


def test_a_declared_entry_carries_its_steam_app_id(config, tmp_path):
    folder = tmp_path / "G"
    folder.mkdir()
    executable = folder / "G.exe"
    executable.write_text("stub")
    config["custom_games"] = [{"name": "G", "executable": str(executable), "steam_appid": "480"}]
    assert library(config)[0].steam_appid == "480"


def test_a_scanned_game_has_no_steam_app_id(config, tmp_path):
    folder = tmp_path / "Scanned"
    folder.mkdir()
    (folder / "Scanned.exe").write_text("stub")
    config["custom_games"] = []
    game = next(g for g in library(config) if g.name == "Scanned")
    assert game.steam_appid == ""


# ---- where a hand-added binary belongs ---------------------------------------


def test_game_folder_uses_the_library_subdirectory(tmp_path):
    """The scan gives a game its library folder, so adding by hand must too.

    Otherwise the same binary gets one prefix from the scan and another from
    being added, and the second opens with none of the first one's saves.
    """
    root = tmp_path / "games"
    executable = root / "Hitman" / "Hitman Absolution" / "HMA.exe"
    executable.parent.mkdir(parents=True)
    executable.write_text("stub")
    assert game_folder(executable, [root]) == root / "Hitman"


def test_game_folder_falls_back_to_the_binarys_own_folder(tmp_path):
    executable = tmp_path / "elsewhere" / "Game.exe"
    executable.parent.mkdir(parents=True)
    executable.write_text("stub")
    assert game_folder(executable, [tmp_path / "games"]) == executable.parent


def test_game_folder_leaves_a_binary_directly_in_a_root_alone(tmp_path):
    executable = tmp_path / "Game.exe"
    executable.write_text("stub")
    assert game_folder(executable, [tmp_path]) == tmp_path


# ---- programs that are not a plain .exe --------------------------------------


ELF = b"\x7fELF\x02\x01\x01\x00" + bytes(8)


def _binary(path, data=ELF):
    path.write_bytes(data)
    path.chmod(0o755)
    return path


def test_a_native_game_is_found_when_there_is_no_windows_program(tmp_path):
    folder = tmp_path / "LinuxGame"
    folder.mkdir()
    binary = _binary(folder / "LinuxGame.x86_64")
    (folder / "readme.txt").write_text("not executable")
    assert select_executable(folder) == binary


def test_a_shell_launcher_counts_as_a_program(tmp_path):
    folder = tmp_path / "Shipped"
    folder.mkdir()
    launcher = _binary(folder / "Shipped", b"#!/bin/sh\nexec ./game\n")
    assert select_executable(folder) == launcher


def test_data_files_with_the_executable_bit_are_not_offered(tmp_path):
    """An Electron build ships every file mode 755, licences and .pak included."""
    folder = tmp_path / "Electron"
    folder.mkdir()
    for name in ("LICENSES.chromium.html", "resources.pak", "icudtl.dat", "libEGL.so", "snapshot_blob.bin"):
        _binary(folder / name, b"not a program at all")
    assert select_executable(folder) is None
    binary = _binary(folder / "Electron")
    assert select_executable(folder) == binary


def test_a_windows_program_is_preferred_over_a_native_one(tmp_path):
    folder = tmp_path / "Both"
    folder.mkdir()
    _binary(folder / "Both")
    (folder / "Both.exe").write_text("stub")
    assert select_executable(folder) == folder / "Both.exe"


def test_a_folder_of_data_offers_nothing(tmp_path):
    folder = tmp_path / "Data"
    folder.mkdir()
    (folder / "readme.txt").write_text("stub")
    assert select_executable(folder) is None


def test_a_batch_launcher_counts_as_a_program(tmp_path):
    folder = tmp_path / "Repack"
    folder.mkdir()
    (folder / "play.bat").write_text("stub")
    assert select_executable(folder) == folder / "play.bat"


def test_an_exe_beats_a_batch_file_of_the_same_name(tmp_path):
    folder = tmp_path / "Repack"
    folder.mkdir()
    (folder / "Repack.bat").write_text("stub")
    (folder / "Repack.exe").write_text("stub")
    assert select_executable(folder) == folder / "Repack.exe"


def test_the_scan_reaches_a_binary_four_levels_down(tmp_path):
    """A repack adds a folder above the usual Unreal Binaries/Win64 layout."""
    folder = tmp_path / "Deep"
    nested = folder / "Repack" / "Game" / "Binaries" / "Win64"
    nested.mkdir(parents=True)
    (nested / "Deep-Win64-Shipping.exe").write_text("stub")
    assert select_executable(folder) == nested / "Deep-Win64-Shipping.exe"


# ---- ordering ----------------------------------------------------------------


def test_sort_games_puts_favourites_first():
    from hvrunner.core.models import Game

    plain = Game("Alpha", "Custom", "/a", "/a/a.exe")
    favourite = Game("Zeta", "Custom", "/z", "/z/z.exe", favorite=True)
    assert [game.name for game in sort_games([plain, favourite])] == ["Zeta", "Alpha"]
