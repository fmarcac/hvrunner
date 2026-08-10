from __future__ import annotations

from pathlib import Path

import pytest

from hvrunner.core.models import Game, HvrunnerError
from hvrunner.core.planning import build_command, plan


def test_gamemode_wraps_the_command(game_factory, config, stub_tools):
    game = game_factory("Plain.exe")
    command, _ = build_command(game, config)
    assert command[0].endswith("gamemoderun")
    assert command[1].endswith("mangohud")


def test_gamemode_can_be_disabled(game_factory, config, stub_tools):
    config["use_gamemode"] = False
    command, _ = build_command(game_factory("Plain.exe"), config)
    assert not command[0].endswith("gamemoderun")
    assert command[0].endswith("mangohud")


def test_launch_args_are_appended(config, stub_tools, tmp_path):
    folder = tmp_path / "G"
    folder.mkdir()
    executable = folder / "Plain.exe"
    executable.write_text("stub")
    game = Game("G", "Custom", str(folder), str(executable), launch_args=("-dx12", "-windowed"))
    command, _ = build_command(game, config)
    assert command[-2:] == ["-dx12", "-windowed"]


def test_prefix_is_created_inside_the_game_folder(game_factory, config, stub_tools):
    game = game_factory("Plain.exe")
    _, env = build_command(game, config)
    prefix = Path(game.install_dir) / ".hvrunner-proton"
    assert env["WINEPREFIX"] == str(prefix)
    assert prefix.is_dir()


def test_missing_proton_is_reported(game_factory, config, stub_tools, tmp_path):
    config["proton_path"] = str(tmp_path / "absent")
    with pytest.raises(HvrunnerError, match="Proton runtime is unavailable"):
        build_command(game_factory("Plain.exe"), config)


def test_proton_path_pointing_at_the_binary_is_accepted(game_factory, config, stub_tools, fake_proton):
    config["proton_path"] = str(fake_proton / "proton")
    _, env = build_command(game_factory("Plain.exe"), config)
    assert env["PROTONPATH"] == str(fake_proton)


def test_missing_umu_is_reported(game_factory, config, stub_tools, tmp_path):
    config["umu_path"] = str(tmp_path / "absent")
    with pytest.raises(HvrunnerError, match="umu is unavailable"):
        build_command(game_factory("Plain.exe"), config)


def test_missing_executable_is_reported(config, stub_tools, tmp_path):
    game = Game("Gone", "Custom", str(tmp_path), str(tmp_path / "gone.exe"))
    with pytest.raises(HvrunnerError, match="game executable is unavailable"):
        build_command(game, config)


def test_a_missing_wrapper_does_not_stop_a_launch(game_factory, config, monkeypatch):
    """Requiring MangoHud made hvrunner unusable on a machine without it."""
    import hvrunner.core.planning as planning

    monkeypatch.setattr(planning.shutil, "which", lambda name: None)
    command, _ = build_command(game_factory("Plain.exe"), config)
    assert command[0].endswith("umu-run")


def test_mangohud_can_be_disabled(game_factory, config, stub_tools):
    config["use_mangohud"] = False
    command, env = build_command(game_factory("Plain.exe"), config)
    assert not any(part.endswith("mangohud") for part in command)
    assert command[0].endswith("gamemoderun")
    assert "MANGOHUD" not in env


def test_disabling_mangohud_overrides_an_inherited_setting(game_factory, config, stub_tools, monkeypatch):
    """The environment is inherited, so leaving MANGOHUD unset is not enough."""
    monkeypatch.setenv("MANGOHUD", "1")
    monkeypatch.setenv("MANGOHUD_CONFIG", "fps")
    config["use_mangohud"] = False
    _, env = build_command(game_factory("Plain.exe"), config)
    assert "MANGOHUD" not in env
    assert "MANGOHUD_CONFIG" not in env


def test_both_wrappers_can_be_disabled(game_factory, config, stub_tools):
    config["use_mangohud"] = False
    config["use_gamemode"] = False
    command, _ = build_command(game_factory("Plain.exe"), config)
    assert command[0].endswith("umu-run")


def test_plan_does_not_touch_the_disk(game_factory, config, stub_tools):
    """The interface previews on every cursor move, so it must be inert."""
    game = game_factory("Plain.exe")
    prepared = plan(game, config)
    assert prepared.prefix_ready is False
    assert not (Path(game.install_dir) / ".hvrunner-proton").exists()


def test_plan_reports_an_existing_prefix(game_factory, config, stub_tools):
    game = game_factory("Plain.exe")
    (Path(game.install_dir) / ".hvrunner-proton").mkdir()
    assert plan(game, config).prefix_ready is True


def test_plan_with_prepare_creates_the_prefix(game_factory, config, stub_tools):
    game = game_factory("Plain.exe")
    plan(game, config, prepare=True)
    assert (Path(game.install_dir) / ".hvrunner-proton").is_dir()


def test_verify_dlss_preview_creates_nothing(game_factory, config, stub_tools, monkeypatch):
    monkeypatch.setenv("ACBF_VERIFY_DLSS", "1")
    game = game_factory("ACBlackFlag.exe", folder="BF")
    plan(game, config)
    assert not (Path(game.install_dir) / "logs").exists()


def test_shader_cache_preview_creates_nothing(game_factory, config, stub_tools):
    game = game_factory("Plain.exe")
    plan(game, config)
    assert not (Path(game.install_dir) / ".hvrunner-proton" / "shadercache").exists()


def test_notable_environment_is_ordered_and_filtered(game_factory, config, stub_tools):
    prepared = plan(game_factory("ACBlackFlag.exe", folder="BF"), config)
    names = [name for name, _ in prepared.notable_environment()]
    assert names[0] == "PROTONPATH"
    assert "DXVK_ENABLE_NVAPI" in names
    assert "VKD3D_SHADER_CACHE_PATH" in names
    # GAMEID is set but is not worth showing.
    assert "GAMEID" not in names
