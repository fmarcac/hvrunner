from __future__ import annotations

from pathlib import Path

import pytest

from hvrunner.core.constants import DEFAULT_MANGOHUD_CONFIG, DEFAULT_WINEDEBUG
from hvrunner.core.models import Game
from hvrunner.core.planning import build_command


def test_wine_errors_are_not_suppressed():
    """err is the only channel that names a DLL whose DllMain faulted.

    Silencing it left a game that died on startup indistinguishable from one
    that launched, which is what made a failed launch impossible to diagnose.
    """
    assert DEFAULT_WINEDEBUG.startswith("err+all")
    assert "fixme-all" in DEFAULT_WINEDEBUG


def test_base_environment(game_factory, config, stub_tools, monkeypatch):
    monkeypatch.delenv("MANGOHUD_CONFIG", raising=False)
    _, env = build_command(game_factory("Plain.exe"), config)
    assert env["MANGOHUD"] == "1"
    assert env["WINEDEBUG"] == DEFAULT_WINEDEBUG
    assert env["DISABLE_GAMESCOPE_WSI"] == "1"
    assert env["PROTON_USE_XALIA"] == "0"


def test_mangohud_config_is_left_unset_by_default(game_factory, config, stub_tools, monkeypatch):
    """Setting it would replace the user's MangoHud.conf rather than merge with it."""
    monkeypatch.delenv("MANGOHUD_CONFIG", raising=False)
    assert DEFAULT_MANGOHUD_CONFIG == ""
    _, env = build_command(game_factory("Plain.exe"), config)
    assert "MANGOHUD_CONFIG" not in env


def test_mangohud_config_is_set_when_configured(game_factory, config, stub_tools, monkeypatch):
    monkeypatch.delenv("MANGOHUD_CONFIG", raising=False)
    config["mangohud_config"] = "fps,frametime"
    _, env = build_command(game_factory("Plain.exe"), config)
    assert env["MANGOHUD_CONFIG"] == "fps,frametime"


def test_environment_override_wins_over_config(game_factory, config, stub_tools, monkeypatch):
    monkeypatch.setenv("MANGOHUD_CONFIG", "sentinel=1")
    config["mangohud_config"] = "ignored"
    _, env = build_command(game_factory("Plain.exe"), config)
    assert env["MANGOHUD_CONFIG"] == "sentinel=1"


def test_default_avoids_the_full_preset():
    """full enables media_player, which logs an error per poll with no MPRIS player."""
    assert "full" not in DEFAULT_MANGOHUD_CONFIG


def test_wayland_toggle(game_factory, config, stub_tools, monkeypatch):
    game = game_factory("Plain.exe")
    config["enable_wayland"] = True
    _, env = build_command(game, config)
    assert env["PROTON_ENABLE_WAYLAND"] == "1"

    config["enable_wayland"] = False
    monkeypatch.setenv("PROTON_ENABLE_WAYLAND", "1")
    _, env = build_command(game, config)
    assert "PROTON_ENABLE_WAYLAND" not in env


def test_extra_env_applied_last(game_factory, config, stub_tools):
    config["extra_env"] = {"WINEDEBUG": "+all", "CUSTOM": "yes"}
    _, env = build_command(game_factory("Plain.exe"), config)
    assert env["WINEDEBUG"] == "+all"
    assert env["CUSTOM"] == "yes"


def test_malformed_extra_env_is_ignored(game_factory, config, stub_tools):
    config["extra_env"] = ["not", "a", "mapping"]
    _, env = build_command(game_factory("Plain.exe"), config)
    assert env["WINEDEBUG"] == DEFAULT_WINEDEBUG


@pytest.mark.parametrize("name", ["ACBlackFlag.exe", "ACBlackFlag_Plus.exe", "acblackflag.EXE"])
def test_black_flag_environment_matches_variants(game_factory, config, stub_tools, name):
    _, env = build_command(game_factory(name, folder="BF"), config)
    assert env["DXVK_ENABLE_NVAPI"] == "1"
    assert env["NVPRESENT_ENABLE_SMOOTH_MOTION"] == "0"


def test_other_games_do_not_get_black_flag_environment(game_factory, config, stub_tools):
    _, env = build_command(game_factory("Other.exe"), config)
    assert "DXVK_ENABLE_NVAPI" not in env


def test_verify_dlss_enables_indicators(game_factory, config, stub_tools, monkeypatch):
    monkeypatch.setenv("ACBF_VERIFY_DLSS", "1")
    _, env = build_command(game_factory("ACBlackFlag.exe", folder="BF"), config)
    assert env["DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS"] == "DLSSIndicator=1024,DLSSGIndicator=2"
    assert env["DXVK_NVAPI_LOG_LEVEL"] == "info"
    assert Path(env["DXVK_NVAPI_LOG_PATH"]).is_dir()


def test_indicators_off_by_default(game_factory, config, stub_tools, monkeypatch):
    monkeypatch.delenv("ACBF_VERIFY_DLSS", raising=False)
    _, env = build_command(game_factory("ACBlackFlag.exe", folder="BF"), config)
    assert env["DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS"] == "DLSSIndicator=0,DLSSGIndicator=0"


def test_shader_cache_paths_are_set_and_created(game_factory, config, stub_tools):
    game = game_factory("Plain.exe")
    _, env = build_command(game, config)
    cache = Path(game.install_dir) / ".hvrunner-proton" / "shadercache"
    # umu only sets STEAM_COMPAT_SHADER_PATH, which vkd3d-proton does not read.
    assert env["VKD3D_SHADER_CACHE_PATH"] == str(cache)
    assert env["DXVK_STATE_CACHE_PATH"] == str(cache)
    assert cache.is_dir()


def test_shader_cache_can_be_disabled(game_factory, config, stub_tools):
    config["shader_cache"] = False
    _, env = build_command(game_factory("Plain.exe"), config)
    assert "VKD3D_SHADER_CACHE_PATH" not in env
    assert "DXVK_STATE_CACHE_PATH" not in env


def test_no_app_id_runs_as_spacewar(game_factory, config, stub_tools):
    """Running as nothing at all is what left steam_api64.dll unable to find Steam."""
    _, env = build_command(game_factory("Plain.exe"), config)
    assert env["SteamAppId"] == "480"
    assert env["PROTON_DISABLE_LSTEAMCLIENT"] == "0"


def test_a_declared_app_id_wins(game_factory, config, stub_tools):
    from dataclasses import replace

    game = replace(game_factory("Plain.exe"), steam_appid="1234")
    _, env = build_command(game, config)
    assert env["SteamAppId"] == "1234"
    assert env["STEAM_COMPAT_APP_ID"] == "1234"


def test_gameid_is_never_set(game_factory, config, stub_tools, monkeypatch):
    """umu's spelling of the id, and the source of the umu-<id> regex trap."""
    monkeypatch.setenv("GAMEID", "umu-9999")
    _, env = build_command(game_factory("Plain.exe"), config)
    assert "GAMEID" not in env


def test_steam_client_path_is_always_passed(game_factory, config, stub_tools, tmp_path):
    """The one name umu blanked, and the cause of every Steam facing failure."""
    steam = tmp_path / "SteamRoot"
    config["steam_root"] = str(steam)
    _, env = build_command(game_factory("Plain.exe"), config)
    assert env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] == str(steam)
    assert env["STEAM_COMPAT_DATA_PATH"] == env["WINEPREFIX"]


def test_a_shipped_appid_beats_spacewar(config, stub_tools, tmp_path):
    """A bundled emulator reads its own steam_settings and ignores the
    environment, so forcing Spacewar put the two ids in contradiction and the
    game exited before its engine started."""
    folder = tmp_path / "Repack"
    settings = folder / "Game_Data" / "Plugins" / "x86_64" / "steam_settings"
    settings.mkdir(parents=True)
    (settings / "steam_appid.txt").write_text("4369130\n")
    executable = folder / "Game.exe"
    executable.write_text("stub")
    game = Game("Repack", "Custom", str(folder), str(executable))
    _, env = build_command(game, config)
    assert env["SteamAppId"] == "4369130"
    assert env["STEAM_COMPAT_APP_ID"] == "4369130"


def test_a_root_appid_file_is_read(config, stub_tools, tmp_path):
    folder = tmp_path / "Rooted"
    folder.mkdir()
    (folder / "steam_appid.txt").write_text("1234")
    executable = folder / "Game.exe"
    executable.write_text("stub")
    game = Game("Rooted", "Custom", str(folder), str(executable))
    _, env = build_command(game, config)
    assert env["SteamAppId"] == "1234"


def test_a_declared_id_beats_a_shipped_one(config, stub_tools, tmp_path):
    from dataclasses import replace

    folder = tmp_path / "Both"
    folder.mkdir()
    (folder / "steam_appid.txt").write_text("4369130")
    executable = folder / "Game.exe"
    executable.write_text("stub")
    game = replace(Game("Both", "Custom", str(folder), str(executable)), steam_appid="480")
    _, env = build_command(game, config)
    assert env["SteamAppId"] == "480"


def test_the_id_is_never_empty(game_factory, config, stub_tools):
    """protonfixes takes its game id from the digits in STEAM_COMPAT_DATA_PATH
    and raises IndexError when there are none, killing the launch."""
    _, env = build_command(game_factory("Plain.exe"), config)
    assert env["SteamAppId"]
    assert env["STEAM_COMPAT_APP_ID"]


def test_a_bundled_fix_beats_the_games_own_settings(config, stub_tools, tmp_path):
    """OnlineFix presents FakeAppId to Steam while telling the game it is
    RealAppId. Reading the game's own id gave Approximately Up 3904850 when its
    fix expected 480."""
    folder = tmp_path / "Fixed"
    settings = folder / "Game_Data" / "Plugins" / "x86_64" / "steam_settings"
    settings.mkdir(parents=True)
    (settings / "steam_appid.txt").write_text("3904850")
    (folder / "OnlineFix.ini").write_text("[Main]\nRealAppId=3904850\nFakeAppId=480\n")
    executable = folder / "Game.exe"
    executable.write_text("stub")
    game = Game("Fixed", "Custom", str(folder), str(executable))
    _, env = build_command(game, config)
    assert env["SteamAppId"] == "480"


def test_unsteam_spells_the_key_with_underscores(config, stub_tools, tmp_path):
    folder = tmp_path / "Unsteamed"
    folder.mkdir()
    (folder / "unsteam.ini").write_text("[game]\nreal_app_id=4450620\nfake_app_id=480\n")
    executable = folder / "Game.exe"
    executable.write_text("stub")
    game = Game("Unsteamed", "Custom", str(folder), str(executable))
    _, env = build_command(game, config)
    assert env["SteamAppId"] == "480"
