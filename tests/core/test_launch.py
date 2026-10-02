from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from hvrunner.core.affinity import all_cpus, game_roots, matching_game_pids, watcher_command
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
    assert recorded["env"]["SteamAppId"] == SPACEWAR_APPID
    assert recorded["env"]["STEAM_COMPAT_APP_ID"] == SPACEWAR_APPID
    assert recorded["env"]["PROTON_DISABLE_LSTEAMCLIENT"] == "0"


def test_a_second_launch_is_refused_while_the_game_runs(config, state_home, stub_tools, monkeypatch, tmp_path):
    """Proton runs with "run" now, so nothing else stops two copies starting.

    Checked against the process table rather than the wineserver socket: Proton
    keeps a wineserver alive after the game exits, so the socket reports a
    prefix as busy long after its game closed.
    """
    import hvrunner.core.launcher as launcher_module
    from hvrunner.core.constants import CUSTOM_SOURCE
    from hvrunner.core.models import Game, HvrunnerError

    folder = tmp_path / "Busy"
    folder.mkdir()
    executable = folder / "Busy.exe"
    executable.write_text("stub")
    game = Game("Busy", CUSTOM_SOURCE, str(folder), str(executable))

    monkeypatch.setattr(launcher_module, "matching_game_pids", lambda name, *roots: [4242])
    with pytest.raises(HvrunnerError, match="already running"):
        launcher_module.launch(game, config)


def test_a_quiet_prefix_still_launches(config, state_home, stub_tools, monkeypatch, tmp_path):
    import hvrunner.core.launcher as launcher_module
    from hvrunner.core.constants import CUSTOM_SOURCE
    from hvrunner.core.models import Game

    class FakePopen:
        def __init__(self, command, **kwargs):
            self.pid = 99

    folder = tmp_path / "Quiet"
    folder.mkdir()
    executable = folder / "Quiet.exe"
    executable.write_text("stub")
    game = Game("Quiet", CUSTOM_SOURCE, str(folder), str(executable))

    monkeypatch.setattr(launcher_module, "matching_game_pids", lambda name, *roots: [])
    monkeypatch.setattr(launcher_module.subprocess, "Popen", FakePopen)
    assert launcher_module.launch(game, config).pid == 99


def test_the_watcher_is_given_the_whole_executable_path(tmp_path):
    """It needs the folder the game runs in as well as the folder it lives in."""
    command = watcher_command("/games/Game/Bin/Game.exe", "/games/Game")
    assert command[-3:] == ["--affinity-watch", "/games/Game/Bin/Game.exe", "/games/Game"]


def test_game_roots_covers_both_folders():
    assert game_roots("/games/Game/Bin/Game.exe", "/games/Game") == ("/games/Game", "/games/Game/Bin")


def test_a_nested_working_directory_still_matches(tmp_path):
    """The bug that silently disabled affinity enforcement.

    launch starts a game in the folder its binary is in, which is a level below
    install_dir whenever the binary is nested, as Hitman's is. Comparing cwd
    against install_dir alone matched nothing at all for those games.
    """
    install_dir = tmp_path / "Game"
    nested = install_dir / "Binaries" / "Win64"
    nested.mkdir(parents=True)
    child = subprocess.Popen(["sleep", "5"], cwd=nested)
    try:
        found: list[int] = []
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            found = matching_game_pids("sleep", str(install_dir))
            if child.pid in found:
                break
            time.sleep(0.02)
        assert child.pid in found
    finally:
        child.kill()
        child.wait()


def test_an_unrelated_directory_does_not_match(tmp_path):
    elsewhere = tmp_path / "Elsewhere"
    elsewhere.mkdir()
    other = tmp_path / "Game"
    other.mkdir()
    child = subprocess.Popen(["sleep", "5"], cwd=elsewhere)
    try:
        time.sleep(0.1)
        assert child.pid not in matching_game_pids("sleep", str(other))
    finally:
        child.kill()
        child.wait()


def test_a_sibling_prefix_is_not_treated_as_containment(tmp_path):
    """ "/games/Game2" must not count as inside "/games/Game"."""
    inside = tmp_path / "Game2"
    inside.mkdir()
    child = subprocess.Popen(["sleep", "5"], cwd=inside)
    try:
        time.sleep(0.1)
        assert child.pid not in matching_game_pids("sleep", str(tmp_path / "Game"))
    finally:
        child.kill()
        child.wait()


def test_a_launch_still_starting_counts_as_running(tmp_path):
    """The double launch: Proton takes a second or two to start the game, and
    the comm/cwd match finds nothing in that window, so a second Enter started
    a second copy. The wrapper is visible from the first instant."""
    from hvrunner.core.affinity import starting_launch_pids

    executable = str(tmp_path / "Game" / "Game.exe")
    wrapper = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(5)", "/opt/proton/proton", "run", executable]
    )
    supervisor = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)", "--affinity-watch", executable])
    try:
        time.sleep(0.1)
        found = starting_launch_pids(executable)
        assert wrapper.pid in found
        # The supervisor names the executable too, and outlives a failed
        # launch; counting it would block relaunching for its whole timeout.
        assert supervisor.pid not in found
        assert starting_launch_pids(str(tmp_path / "Other" / "Game.exe")) == []
    finally:
        for child in (wrapper, supervisor):
            child.kill()
            child.wait()


def test_launch_refuses_while_the_previous_launch_is_starting(config, state_home, stub_tools, monkeypatch, tmp_path):
    import hvrunner.core.launcher as launcher_module
    from hvrunner.core.constants import CUSTOM_SOURCE
    from hvrunner.core.models import Game, HvrunnerError

    folder = tmp_path / "Slow"
    folder.mkdir()
    executable = folder / "Slow.exe"
    executable.write_text("stub")
    game = Game("Slow", CUSTOM_SOURCE, str(folder), str(executable))

    monkeypatch.setattr(launcher_module, "matching_game_pids", lambda name, *roots: [])
    monkeypatch.setattr(launcher_module, "starting_launch_pids", lambda path: [4243])
    with pytest.raises(HvrunnerError, match="already starting"):
        launcher_module.launch(game, config)
