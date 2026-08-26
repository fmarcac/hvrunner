from __future__ import annotations

from pathlib import Path

import pytest

from hvrunner.core.models import Game, HvrunnerError
from hvrunner.core.planning import plan


def test_gamemode_wraps_the_command(game_factory, config, stub_tools):
    game = game_factory("Plain.exe")
    command = plan(game, config, prepare=True).command
    assert command[0].endswith("gamemoderun")
    assert command[1].endswith("mangohud")


def test_gamemode_can_be_disabled(game_factory, config, stub_tools):
    config["use_gamemode"] = False
    command = plan(game_factory("Plain.exe"), config, prepare=True).command
    assert not command[0].endswith("gamemoderun")
    assert command[0].endswith("mangohud")


def test_launch_args_are_appended(config, stub_tools, tmp_path):
    folder = tmp_path / "G"
    folder.mkdir()
    executable = folder / "Plain.exe"
    executable.write_text("stub")
    game = Game("G", "Custom", str(folder), str(executable), launch_args=("-dx12", "-windowed"))
    command = plan(game, config, prepare=True).command
    assert command[-2:] == ["-dx12", "-windowed"]


def test_prefix_is_created_inside_the_game_folder(game_factory, config, stub_tools):
    game = game_factory("Plain.exe")
    env = plan(game, config, prepare=True).environment
    prefix = Path(game.install_dir) / ".hvrunner-proton"
    assert env["WINEPREFIX"] == str(prefix)
    assert prefix.is_dir()


def test_missing_proton_is_reported(game_factory, config, stub_tools, tmp_path):
    config["proton_path"] = str(tmp_path / "absent")
    with pytest.raises(HvrunnerError, match="Proton runtime is unavailable"):
        plan(game_factory("Plain.exe"), config, prepare=True)


def test_proton_path_pointing_at_the_binary_is_accepted(game_factory, config, stub_tools, fake_proton):
    config["proton_path"] = str(fake_proton / "proton")
    env = plan(game_factory("Plain.exe"), config, prepare=True).environment
    assert env["PROTONPATH"] == str(fake_proton)


def test_missing_executable_is_reported(config, stub_tools, tmp_path):
    game = Game("Gone", "Custom", str(tmp_path), str(tmp_path / "gone.exe"))
    with pytest.raises(HvrunnerError, match="game executable is unavailable"):
        plan(game, config, prepare=True)


def test_a_missing_wrapper_does_not_stop_a_launch(game_factory, config, monkeypatch):
    """Requiring MangoHud made hvrunner unusable on a machine without it."""
    import hvrunner.core.planning as planning

    monkeypatch.setattr(planning.shutil, "which", lambda name: None)
    command = plan(game_factory("Plain.exe"), config, prepare=True).command
    assert command[0].endswith("proton")


def test_mangohud_can_be_disabled(game_factory, config, stub_tools):
    config["use_mangohud"] = False
    prepared = plan(game_factory("Plain.exe"), config, prepare=True)
    command, env = prepared.command, prepared.environment
    assert not any(part.endswith("mangohud") for part in command)
    assert command[0].endswith("gamemoderun")
    assert "MANGOHUD" not in env


def test_disabling_mangohud_overrides_an_inherited_setting(game_factory, config, stub_tools, monkeypatch):
    """The environment is inherited, so leaving MANGOHUD unset is not enough."""
    monkeypatch.setenv("MANGOHUD", "1")
    monkeypatch.setenv("MANGOHUD_CONFIG", "fps")
    config["use_mangohud"] = False
    env = plan(game_factory("Plain.exe"), config, prepare=True).environment
    assert "MANGOHUD" not in env
    assert "MANGOHUD_CONFIG" not in env


def test_both_wrappers_can_be_disabled(game_factory, config, stub_tools):
    config["use_mangohud"] = False
    config["use_gamemode"] = False
    command = plan(game_factory("Plain.exe"), config, prepare=True).command
    assert command[0].endswith("proton")


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
    # The pane answers "what will actually run", so the id the game presents
    # as and the Steam directory Proton populates both belong in it.
    assert "SteamAppId" in names
    assert "STEAM_COMPAT_CLIENT_INSTALL_PATH" in names


def test_every_game_runs_through_proton(game_factory, config, stub_tools, fake_proton):
    """umu is gone. It blanked STEAM_COMPAT_CLIENT_INSTALL_PATH, and every
    Steam facing failure this launcher had came from that."""
    game = game_factory("Plain.exe")
    command = plan(game, config, prepare=True).command
    assert command[-3:] == [str(fake_proton / "proton"), "run", game.executable]


def test_prepare_creates_the_prefix_and_links_pfx(game_factory, config, stub_tools):
    """Proton uses <STEAM_COMPAT_DATA_PATH>/pfx as the WINEPREFIX.

    Without the link it builds a second prefix one level down and the game
    opens with none of its saves. installer.discover walks the same path.
    """
    prepared = plan(game_factory("Plain.exe"), config, prepare=True)
    assert prepared.prefix.is_dir()
    link = prepared.prefix / "pfx"
    assert link.is_symlink()
    assert link.resolve() == prepared.prefix.resolve()


def test_preview_still_touches_nothing(game_factory, config, stub_tools):
    prepared = plan(game_factory("Plain.exe"), config)
    assert not prepared.prefix.exists()


def test_proton_is_run_not_waited_on(game_factory, config, stub_tools):
    """waitforexitandrun blocks until the prefix is empty and prints nothing
    while it waits, so a launch into a busy prefix hung and read as a failure."""
    command = plan(game_factory("Plain.exe"), config, prepare=True).command
    assert "run" in command
    assert "waitforexitandrun" not in command


def test_a_game_can_name_its_own_proton(config, stub_tools, tmp_path):
    """Wine features differ between builds, and a game whose plugin wants a
    WinRT class the configured build lacks has nowhere else to say so."""
    other = tmp_path / "OtherProton"
    other.mkdir()
    (other / "proton").write_text("stub")
    (other / "toolmanifest.vdf").write_text("stub")
    folder = tmp_path / "Picky"
    folder.mkdir()
    executable = folder / "Picky.exe"
    executable.write_text("stub")
    game = Game("Picky", "Custom", str(folder), str(executable), proton_path=str(other))
    prepared = plan(game, config, prepare=True)
    command, env = prepared.command, prepared.environment
    assert env["PROTONPATH"] == str(other)
    assert command[-3] == str(other / "proton")


def test_without_one_the_configured_build_is_used(game_factory, config, stub_tools, fake_proton):
    env = plan(game_factory("Plain.exe"), config, prepare=True).environment
    assert env["PROTONPATH"] == str(fake_proton)


# ---- programs that are not a plain .exe -------------------------------------


def _native(tmp_path, name="start.sh", executable=True):
    from hvrunner.core.constants import CUSTOM_SOURCE

    folder = tmp_path / "Native"
    folder.mkdir(exist_ok=True)
    binary = folder / name
    binary.write_text("#!/bin/sh\nexit 0\n")
    if executable:
        binary.chmod(0o755)
    return Game("Native", CUSTOM_SOURCE, str(folder), str(binary))


def test_a_native_binary_runs_without_proton(config, stub_tools, tmp_path, monkeypatch):
    for name in ("PROTONPATH", "WINEPREFIX", "STEAM_COMPAT_DATA_PATH", "SteamAppId"):
        monkeypatch.delenv(name, raising=False)
    prepared = plan(_native(tmp_path), config, prepare=True)
    assert prepared.prefix is None
    assert not any("proton" in part.casefold() for part in prepared.command)
    assert prepared.command[-1].endswith("start.sh")
    assert "STEAM_COMPAT_DATA_PATH" not in prepared.environment
    assert "WINEPREFIX" not in prepared.environment


def test_a_native_binary_still_gets_the_wrappers(config, stub_tools, tmp_path):
    command = plan(_native(tmp_path), config, prepare=True).command
    assert command[0].endswith("gamemoderun")
    assert command[1].endswith("mangohud")


def test_a_native_launch_builds_no_prefix(config, stub_tools, tmp_path):
    game = _native(tmp_path)
    plan(game, config, prepare=True)
    assert not (Path(game.install_dir) / config["custom_prefix_name"]).exists()


def test_a_file_that_is_not_executable_is_refused(config, stub_tools, tmp_path):
    game = _native(tmp_path, name="data.bin", executable=False)
    with pytest.raises(HvrunnerError, match="not executable"):
        plan(game, config, prepare=True)


def test_a_batch_file_goes_through_cmd(game_factory, config, stub_tools):
    command = plan(game_factory("play.bat"), config, prepare=True).command
    # A bare filename, because cmd does not take a unix path and the launcher
    # already starts it in the file's own folder.
    assert command[-3:] == ["cmd", "/c", "play.bat"]


def test_an_msi_goes_through_msiexec(game_factory, config, stub_tools):
    command = plan(game_factory("Setup.msi"), config, prepare=True).command
    assert command[-3:] == ["msiexec", "/i", "Setup.msi"]


def test_an_exe_is_handed_over_by_path(game_factory, config, stub_tools):
    game = game_factory("Plain.exe")
    command = plan(game, config, prepare=True).command
    assert command[-1] == game.executable


# ---- resolving the Proton build ---------------------------------------------


def test_a_build_directory_named_proton_is_not_stripped(game_factory, config, stub_tools, tmp_path):
    """The last component being "proton" does not make it the proton script."""
    build = tmp_path / "compat" / "proton"
    build.mkdir(parents=True)
    (build / "proton").write_text("stub")
    (build / "toolmanifest.vdf").write_text("stub")
    config["proton_path"] = str(build)
    assert plan(game_factory("Plain.exe"), config, prepare=True).environment["PROTONPATH"] == str(build)


def test_an_unusable_build_is_named_as_the_user_wrote_it(game_factory, config, stub_tools, tmp_path):
    config["proton_path"] = str(tmp_path / "nowhere" / "proton")
    with pytest.raises(HvrunnerError, match="nowhere/proton"):
        plan(game_factory("Plain.exe"), config, prepare=True)


# ---- per entry environment ---------------------------------------------------


def test_an_entrys_environment_is_applied_last(game_factory, config, stub_tools):
    from dataclasses import replace

    game = replace(game_factory("Plain.exe"), env=(("DXVK_HUD", "fps"), ("WINEDEBUG", "-all")))
    env = plan(game, config, prepare=True).environment
    assert env["DXVK_HUD"] == "fps"
    # It wins over what hvrunner sets, which is the point of it.
    assert env["WINEDEBUG"] == "-all"


def test_an_entrys_environment_beats_the_global_one(game_factory, config, stub_tools):
    from dataclasses import replace

    config["extra_env"] = {"SHARED": "global"}
    game = replace(game_factory("Plain.exe"), env=(("SHARED", "entry"),))
    assert plan(game, config, prepare=True).environment["SHARED"] == "entry"


def test_a_native_launch_takes_the_entrys_environment_too(config, stub_tools, tmp_path):
    from dataclasses import replace

    game = replace(_native(tmp_path), env=(("SDL_VIDEODRIVER", "wayland"),))
    assert plan(game, config, prepare=True).environment["SDL_VIDEODRIVER"] == "wayland"
