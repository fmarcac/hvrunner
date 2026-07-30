from __future__ import annotations

from pathlib import Path

import pytest

from hvrunner.affinity import all_cpus, watcher_command
from hvrunner.constants import DEFAULT_MANGOHUD_CONFIG
from hvrunner.launcher import build_command, launch, plan
from hvrunner.models import Game, HvrunnerError


def make_game(folder: Path, name: str = "ACBlackFlag.exe") -> Game:
    folder.mkdir(parents=True, exist_ok=True)
    executable = folder / name
    executable.write_text("stub")
    return Game(folder.name, "Custom", str(folder), str(executable))


def test_environment_defaults(tmp_path, config, stub_tools, monkeypatch):
    monkeypatch.delenv("MANGOHUD_CONFIG", raising=False)
    _, env = build_command(make_game(tmp_path / "G", "Plain.exe"), config)
    assert env["MANGOHUD"] == "1"
    assert env["MANGOHUD_CONFIG"] == DEFAULT_MANGOHUD_CONFIG
    assert env["WINEDEBUG"] == "-all"
    assert env["DISABLE_GAMESCOPE_WSI"] == "1"


def test_environment_mangohud_config_override_wins(tmp_path, config, stub_tools, monkeypatch):
    monkeypatch.setenv("MANGOHUD_CONFIG", "sentinel=1")
    _, env = build_command(make_game(tmp_path / "G", "Plain.exe"), config)
    assert env["MANGOHUD_CONFIG"] == "sentinel=1"


def test_default_mangohud_config_avoids_full_preset():
    """full enables media_player, which spams playerctld errors."""
    assert "full" not in DEFAULT_MANGOHUD_CONFIG


def test_wayland_toggle(tmp_path, config, stub_tools, monkeypatch):
    game = make_game(tmp_path / "G", "Plain.exe")
    config["enable_wayland"] = True
    _, env = build_command(game, config)
    assert env["PROTON_ENABLE_WAYLAND"] == "1"

    config["enable_wayland"] = False
    monkeypatch.setenv("PROTON_ENABLE_WAYLAND", "1")
    _, env = build_command(game, config)
    assert "PROTON_ENABLE_WAYLAND" not in env


def test_extra_env_applied_last(tmp_path, config, stub_tools):
    config["extra_env"] = {"WINEDEBUG": "+all", "CUSTOM": "yes"}
    _, env = build_command(make_game(tmp_path / "G", "Plain.exe"), config)
    assert env["WINEDEBUG"] == "+all"
    assert env["CUSTOM"] == "yes"


@pytest.mark.parametrize("name", ["ACBlackFlag.exe", "ACBlackFlag_Plus.exe", "acblackflag.EXE"])
def test_black_flag_environment_matches_variants(tmp_path, config, stub_tools, name):
    _, env = build_command(make_game(tmp_path / "BF", name), config)
    assert env["DXVK_ENABLE_NVAPI"] == "1"
    assert env["NVPRESENT_ENABLE_SMOOTH_MOTION"] == "0"


def test_other_games_do_not_get_black_flag_environment(tmp_path, config, stub_tools):
    _, env = build_command(make_game(tmp_path / "Other", "Other.exe"), config)
    assert "DXVK_ENABLE_NVAPI" not in env


def test_verify_dlss_enables_indicators(tmp_path, config, stub_tools, monkeypatch):
    monkeypatch.setenv("ACBF_VERIFY_DLSS", "1")
    game = make_game(tmp_path / "BF", "ACBlackFlag.exe")
    _, env = build_command(game, config)
    assert env["DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS"] == "DLSSIndicator=1024,DLSSGIndicator=2"
    assert env["DXVK_NVAPI_LOG_LEVEL"] == "info"
    assert Path(env["DXVK_NVAPI_LOG_PATH"]).is_dir()


def test_indicators_off_by_default(tmp_path, config, stub_tools, monkeypatch):
    monkeypatch.delenv("ACBF_VERIFY_DLSS", raising=False)
    _, env = build_command(make_game(tmp_path / "BF", "ACBlackFlag.exe"), config)
    assert env["DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS"] == "DLSSIndicator=0,DLSSGIndicator=0"


def test_gamemode_toggle(tmp_path, config, stub_tools):
    game = make_game(tmp_path / "G", "Plain.exe")
    command, _ = build_command(game, config)
    assert command[0].endswith("gamemoderun")

    config["use_gamemode"] = False
    command, _ = build_command(game, config)
    assert not command[0].endswith("gamemoderun")
    assert command[0].endswith("mangohud")


def test_prefix_is_created_inside_the_game_folder(tmp_path, config, stub_tools):
    folder = tmp_path / "G"
    game = make_game(folder, "Plain.exe")
    _, env = build_command(game, config)
    assert env["WINEPREFIX"] == str(folder / ".hvrunner-proton")
    assert (folder / ".hvrunner-proton").is_dir()


def test_missing_proton_is_reported(tmp_path, config, stub_tools):
    config["proton_path"] = str(tmp_path / "absent")
    with pytest.raises(HvrunnerError, match="Proton runtime is unavailable"):
        build_command(make_game(tmp_path / "G", "Plain.exe"), config)


def test_proton_path_pointing_at_the_binary_is_accepted(tmp_path, config, stub_tools, fake_proton):
    config["proton_path"] = str(fake_proton / "proton")
    _, env = build_command(make_game(tmp_path / "G", "Plain.exe"), config)
    assert env["PROTONPATH"] == str(fake_proton)


def test_missing_umu_is_reported(tmp_path, config, stub_tools):
    config["umu_path"] = str(tmp_path / "absent")
    with pytest.raises(HvrunnerError, match="umu is unavailable"):
        build_command(make_game(tmp_path / "G", "Plain.exe"), config)


def test_missing_executable_is_reported(tmp_path, config, stub_tools):
    game = Game("Gone", "Custom", str(tmp_path), str(tmp_path / "gone.exe"))
    with pytest.raises(HvrunnerError, match="game executable is unavailable"):
        build_command(game, config)


def test_missing_mangohud_is_reported(tmp_path, config, monkeypatch):
    import hvrunner.launcher as launcher

    monkeypatch.setattr(launcher.shutil, "which", lambda name: None)
    with pytest.raises(HvrunnerError, match="MangoHud is unavailable"):
        build_command(make_game(tmp_path / "G", "Plain.exe"), config)


def test_launch_failure_raises_hvrunner_error(tmp_path, config, state_home, monkeypatch):
    """Popen raises OSError on a missing binary, which the interface would not catch."""
    import hvrunner.launcher as launcher

    monkeypatch.setattr(launcher.shutil, "which", lambda name: "/nonexistent/bin/mangohud")
    config["enforce_all_cpus"] = False
    config["use_gamemode"] = False
    game = make_game(tmp_path / "G", "Plain.exe")
    with pytest.raises(HvrunnerError, match="cannot start"):
        launch(game, config)


def test_launch_writes_a_log(tmp_path, config, state_home, monkeypatch):
    import hvrunner.launcher as launcher

    monkeypatch.setattr(launcher.shutil, "which", lambda name: "/bin/true" if name == "mangohud" else None)
    config["enforce_all_cpus"] = False
    config["use_gamemode"] = False
    game = make_game(tmp_path / "G", "Plain.exe")
    result = launch(game, config)
    assert result.pid > 0
    assert result.log_path.is_file()
    assert result.log_path.read_text().startswith("$ ")


def test_plan_does_not_touch_the_disk(tmp_path, config, stub_tools):
    """The interface previews on every cursor move, so it must be inert."""
    folder = tmp_path / "G"
    game = make_game(folder, "Plain.exe")
    prepared = plan(game, config)
    assert prepared.prefix_ready is False
    assert not (folder / ".hvrunner-proton").exists()


def test_plan_reports_an_existing_prefix(tmp_path, config, stub_tools):
    folder = tmp_path / "G"
    game = make_game(folder, "Plain.exe")
    (folder / ".hvrunner-proton").mkdir()
    assert plan(game, config).prefix_ready is True


def test_plan_with_prepare_creates_the_prefix(tmp_path, config, stub_tools):
    folder = tmp_path / "G"
    game = make_game(folder, "Plain.exe")
    plan(game, config, prepare=True)
    assert (folder / ".hvrunner-proton").is_dir()


def test_verify_dlss_preview_creates_nothing(tmp_path, config, stub_tools, monkeypatch):
    monkeypatch.setenv("ACBF_VERIFY_DLSS", "1")
    folder = tmp_path / "BF"
    game = make_game(folder, "ACBlackFlag.exe")
    plan(game, config)
    assert not (folder / "logs").exists()


def test_notable_environment_is_ordered_and_filtered(tmp_path, config, stub_tools):
    prepared = plan(make_game(tmp_path / "BF", "ACBlackFlag.exe"), config)
    names = [name for name, _ in prepared.notable_environment()]
    assert names[0] == "PROTONPATH"
    assert "DXVK_ENABLE_NVAPI" in names
    # GAMEID is set but is not worth showing.
    assert "GAMEID" not in names


def test_all_cpus_ignores_the_caller_mask():
    import os

    assert all_cpus() == set(range(os.cpu_count() or 1))


def test_watcher_command_targets_a_real_entry_point():
    command = watcher_command("Game.exe", "/games/Game")
    assert command[-3:] == ["--affinity-watch", "Game.exe", "/games/Game"]
    target = Path(command[0] if command[0].endswith("hvrunner") else command[1])
    assert target.exists()
