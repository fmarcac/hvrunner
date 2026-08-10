from __future__ import annotations

from pathlib import Path

import pytest

from hvrunner.core.constants import DEFAULT_MANGOHUD_CONFIG, DEFAULT_WINEDEBUG
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


def test_game_id_needs_the_umu_prefix():
    """umu only reads an id out of a GAMEID matching ^umu-[\\d\\w]+$."""
    from hvrunner.core.environment import game_id

    assert game_id("480") == "umu-480"
    assert game_id("") == "0"


def test_no_app_id_leaves_the_proton_default_alone(game_factory, config, stub_tools):
    _, env = build_command(game_factory("Plain.exe"), config)
    assert env["GAMEID"] == "0"
    assert "PROTON_DISABLE_LSTEAMCLIENT" not in env


def test_an_app_id_sets_gameid_and_enables_the_bridge(game_factory, config, stub_tools):
    """This Proton build disables lsteamclient itself unless the name is set."""
    from dataclasses import replace

    game = replace(game_factory("Plain.exe"), steam_appid="480")
    _, env = build_command(game, config)
    assert env["GAMEID"] == "umu-480"
    assert env["PROTON_DISABLE_LSTEAMCLIENT"] == "0"
