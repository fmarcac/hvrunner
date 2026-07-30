from __future__ import annotations

import os
from pathlib import Path

import pytest

from hvrunner.affinity import all_cpus, watcher_command
from hvrunner.display import Monitor
from hvrunner.launcher import drop_to_native_scale, launch
from hvrunner.models import HvrunnerError


def test_launch_failure_raises_hvrunner_error(game_factory, config, state_home, monkeypatch):
    """Popen raises OSError on a missing binary, which the interface would not catch."""
    import hvrunner.planning as planning

    monkeypatch.setattr(planning.shutil, "which", lambda name: "/nonexistent/bin/mangohud")
    config["enforce_all_cpus"] = False
    config["use_gamemode"] = False
    with pytest.raises(HvrunnerError, match="cannot start"):
        launch(game_factory("Plain.exe"), config)


def test_launch_writes_a_log(game_factory, config, state_home, monkeypatch):
    import hvrunner.planning as planning

    monkeypatch.setattr(planning.shutil, "which", lambda name: "/bin/true" if name == "mangohud" else None)
    config["enforce_all_cpus"] = False
    config["use_gamemode"] = False
    result = launch(game_factory("Plain.exe"), config)
    assert result.pid > 0
    assert result.log_path.is_file()
    # The command is recorded first, so a log identifies its own launch.
    assert result.log_path.read_text().startswith("$ ")


def test_native_scale_off_changes_nothing(config, monkeypatch):
    import hvrunner.launcher as launcher

    applied: list[str] = []
    monkeypatch.setattr(launcher.display, "available", lambda: True)
    monkeypatch.setattr(launcher.display, "apply", lambda spec: applied.append(spec) or True)
    assert drop_to_native_scale(config) is None
    assert applied == []


def test_native_scale_drops_and_reports_the_restore_spec(config, monkeypatch):
    import hvrunner.launcher as launcher

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
    import hvrunner.launcher as launcher

    config["native_scale"] = True
    monkeypatch.setattr(launcher.display, "available", lambda: True)
    monkeypatch.setattr(launcher.display, "focused_monitor", lambda: Monitor("DP-3", 2560, 1440, 200.0, 0, 0, 1.0))
    monkeypatch.setattr(launcher.display, "apply", lambda spec: True)
    assert drop_to_native_scale(config) is None


def test_native_scale_without_hyprctl(config, monkeypatch):
    import hvrunner.launcher as launcher

    config["native_scale"] = True
    monkeypatch.setattr(launcher.display, "available", lambda: False)
    assert drop_to_native_scale(config) is None


def test_native_scale_reports_nothing_when_apply_fails(config, monkeypatch):
    """A failed change must not leave a restore spec claiming one happened."""
    import hvrunner.launcher as launcher

    config["native_scale"] = True
    monkeypatch.setattr(launcher.display, "available", lambda: True)
    monkeypatch.setattr(launcher.display, "focused_monitor", lambda: Monitor("DP-3", 2560, 1440, 200.0, 0, 0, 1.25))
    monkeypatch.setattr(launcher.display, "apply", lambda spec: False)
    assert drop_to_native_scale(config) is None


def test_all_cpus_ignores_the_caller_mask():
    assert all_cpus() == set(range(os.cpu_count() or 1))


def test_watcher_command_targets_a_real_entry_point():
    command = watcher_command("Game.exe", "/games/Game")
    assert command[-3:] == ["--affinity-watch", "Game.exe", "/games/Game"]
    target = Path(command[0] if command[0].endswith("hvrunner") else command[1])
    assert target.exists()
