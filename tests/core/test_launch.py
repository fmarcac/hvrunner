from __future__ import annotations

import os
from pathlib import Path

import pytest

from hvrunner.core.affinity import all_cpus, watcher_command
from hvrunner.core.display import Monitor
from hvrunner.core.launcher import alive, drop_to_native_scale, launch
from hvrunner.core.models import HvrunnerError


def test_launch_failure_raises_hvrunner_error(game_factory, config, state_home, monkeypatch):
    """Popen raises OSError on a missing binary, which the interface would not catch."""
    import hvrunner.core.planning as planning

    monkeypatch.setattr(planning.shutil, "which", lambda name: "/nonexistent/bin/mangohud")
    config["enforce_all_cpus"] = False
    config["use_gamemode"] = False
    with pytest.raises(HvrunnerError, match="cannot start"):
        launch(game_factory("Plain.exe"), config)


def test_launch_writes_a_log(game_factory, config, state_home, monkeypatch):
    import hvrunner.core.planning as planning

    monkeypatch.setattr(planning.shutil, "which", lambda name: "/bin/true" if name == "mangohud" else None)
    config["enforce_all_cpus"] = False
    config["use_gamemode"] = False
    result = launch(game_factory("Plain.exe"), config)
    assert result.pid > 0
    assert result.log_path.is_file()
    # The command is recorded first, so a log identifies its own launch.
    assert result.log_path.read_text().startswith("$ ")


def test_native_scale_off_changes_nothing(config, monkeypatch):
    import hvrunner.core.launcher as launcher

    applied: list[str] = []
    monkeypatch.setattr(launcher.display, "available", lambda: True)
    monkeypatch.setattr(launcher.display, "apply", lambda spec: applied.append(spec) or True)
    assert drop_to_native_scale(config) is None
    assert applied == []


def test_native_scale_drops_and_reports_the_restore_spec(config, monkeypatch):
    import hvrunner.core.launcher as launcher

    config["native_scale"] = True
    monitor = Monitor("DP-3", 2560, 1440, 200.013, 0, 0, 1.25)
    applied: list[str] = []
    monkeypatch.setattr(launcher.display, "available", lambda: True)
    monkeypatch.setattr(launcher.display, "focused_monitor", lambda: monitor)
    monkeypatch.setattr(launcher.display, "apply", lambda spec: applied.append(spec) or True)

    restore = drop_to_native_scale(config)
    assert applied == ["DP-3,2560x1440@200.013,0x0,1"]
    assert restore == "DP-3,2560x1440@200.013,0x0,1.25"


def test_native_scale_skips_an_unscaled_output(config, monkeypatch):
    import hvrunner.core.launcher as launcher

    config["native_scale"] = True
    monkeypatch.setattr(launcher.display, "available", lambda: True)
    monkeypatch.setattr(launcher.display, "focused_monitor", lambda: Monitor("DP-3", 2560, 1440, 200.0, 0, 0, 1.0))
    monkeypatch.setattr(launcher.display, "apply", lambda spec: True)
    assert drop_to_native_scale(config) is None


def test_native_scale_without_hyprctl(config, monkeypatch):
    import hvrunner.core.launcher as launcher

    config["native_scale"] = True
    monkeypatch.setattr(launcher.display, "available", lambda: False)
    assert drop_to_native_scale(config) is None


def test_native_scale_reports_nothing_when_apply_fails(config, monkeypatch):
    """A failed change must not leave a restore spec claiming one happened."""
    import hvrunner.core.launcher as launcher

    config["native_scale"] = True
    monkeypatch.setattr(launcher.display, "available", lambda: True)
    monkeypatch.setattr(launcher.display, "focused_monitor", lambda: Monitor("DP-3", 2560, 1440, 200.0, 0, 0, 1.25))
    monkeypatch.setattr(launcher.display, "apply", lambda spec: False)
    assert drop_to_native_scale(config) is None


def test_alive_follows_a_process_that_ends():
    """SIGCHLD is SIG_IGN, so this cannot go through Popen.poll."""
    import subprocess

    process = subprocess.Popen(["/bin/sleep", "30"])
    try:
        assert alive(process.pid)
    finally:
        process.kill()
        process.wait()
    assert not alive(process.pid)


def test_all_cpus_ignores_the_caller_mask():
    assert all_cpus() == set(range(os.cpu_count() or 1))


def test_watcher_command_targets_a_real_entry_point():
    command = watcher_command("Game.exe", "/games/Game")
    assert command[-3:] == ["--affinity-watch", "Game.exe", "/games/Game"]
    target = Path(command[0] if command[0].endswith("hvrunner") else command[1])
    assert target.exists()


def test_launch_runs_in_the_executables_own_folder(config, state_home, stub_tools, monkeypatch, tmp_path):
    """A scanned game's binary can sit below the folder the prefix lives in.

    Hitman ships ".../Hitman-Absolution-AnkerGames/Hitman Absolution/HMA.exe",
    so cwd and install_dir are not the same directory.
    """
    import hvrunner.core.launcher as launcher
    from hvrunner.core.constants import CUSTOM_SOURCE
    from hvrunner.core.models import Game

    recorded: dict = {}

    class FakePopen:
        def __init__(self, command, **kwargs):
            recorded["command"] = command
            recorded.update(kwargs)
            self.pid = 4242

    monkeypatch.setattr(launcher.subprocess, "Popen", FakePopen)
    config["enforce_all_cpus"] = False

    folder = tmp_path / "Game"
    inner = folder / "Deep"
    inner.mkdir(parents=True)
    executable = inner / "Game.exe"
    executable.write_text("stub")

    launch(Game("Game", CUSTOM_SOURCE, str(folder), str(executable)), config)

    assert recorded["cwd"] == str(inner)
    # install_dir keeps its own meaning: it is where the prefix lives.
    assert recorded["env"]["WINEPREFIX"] == str(folder / ".hvrunner-proton")


def test_working_directory_is_the_binarys_parent():
    from hvrunner.core.launcher import working_directory

    assert working_directory("/games/Title/Sub/Game.exe") == "/games/Title/Sub"


def test_spacewar_launch_overrides_a_stored_id(config, state_home, stub_tools, monkeypatch, tmp_path):
    """S is a one off: it ignores whatever the entry stores."""
    from dataclasses import replace

    import hvrunner.core.launcher as launcher
    from hvrunner.core.constants import CUSTOM_SOURCE, SPACEWAR_APPID
    from hvrunner.core.models import Game

    recorded: dict = {}

    class FakePopen:
        def __init__(self, command, **kwargs):
            recorded.update(kwargs)
            self.pid = 4242

    monkeypatch.setattr(launcher.subprocess, "Popen", FakePopen)
    config["enforce_all_cpus"] = False

    folder = tmp_path / "Game"
    folder.mkdir()
    executable = folder / "Game.exe"
    executable.write_text("stub")
    stored = Game("Game", CUSTOM_SOURCE, str(folder), str(executable), steam_appid="1234")

    launch(replace(stored, steam_appid=SPACEWAR_APPID), config)
    assert recorded["env"]["GAMEID"] == "umu-480"
    assert recorded["env"]["PROTON_DISABLE_LSTEAMCLIENT"] == "0"
