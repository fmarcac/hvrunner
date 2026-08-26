"""Starting a game and handing it to a supervisor."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import display
from . import prefix as prefix_module
from .affinity import game_roots, matching_game_pids, watcher_command
from .constants import ENFORCE_AFFINITY_ENV, RESTORE_MONITOR_ENV
from .logs import new_log_path, prune_logs
from .models import Game, HvrunnerError
from .planning import plan, resolve_proton


@dataclass(frozen=True)
class LaunchResult:
    pid: int
    log_path: Path


def alive(pid: int) -> bool:
    """True while a launched process still exists.

    Popen.poll and Popen.wait cannot answer this: cli.main sets SIGCHLD to
    SIG_IGN so the kernel reaps children itself, after which wait raises
    ChildProcessError and poll never reports a status. One definition, because
    the installer asks the same question.
    """
    return Path(f"/proc/{pid}").exists()


def working_directory(executable: str) -> str:
    """Where a game starts: the folder its binary is in.

    Not install_dir. A scanned game's executable can sit a level below the game
    folder, as Hitman's does in "Hitman Absolution/HMA.exe", and a game that
    opens data files relative to the working directory would not find them.
    install_dir keeps its one meaning, which is where the Proton prefix lives.
    """
    return str(Path(executable).parent)


def reap_children_automatically() -> None:
    """Let the kernel reap exited children.

    start_new_session does not reparent, so without this every launched game and
    every finished supervisor stays a zombie for the lifetime of the UI.
    """
    with contextlib.suppress(ValueError, OSError, AttributeError):
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)


def drop_to_native_scale(config: dict[str, Any]) -> str | None:
    """Set the output to scale 1, returning the spec that restores it.

    Returns None when nothing was changed, which is also what the caller wants
    when hyprctl is absent or the output is already unscaled.
    """
    if not config.get("native_scale") or not display.available():
        return None
    monitor = display.focused_monitor()
    if monitor is None or not monitor.scaled:
        return None
    restore = monitor.spec(monitor.scale)
    if not display.apply(monitor.spec(1.0)):
        return None
    return restore


def _start_supervisor(game: Game, config: dict[str, Any], restore_monitor: str | None) -> None:
    enforce = bool(config.get("enforce_all_cpus", True))
    # The supervisor is also what restores the output scale, so it has to run
    # whenever either job is outstanding.
    if not enforce and not restore_monitor:
        return
    supervisor_env = os.environ.copy()
    supervisor_env[ENFORCE_AFFINITY_ENV] = "1" if enforce else "0"
    if restore_monitor:
        supervisor_env[RESTORE_MONITOR_ENV] = restore_monitor
    try:
        subprocess.Popen(
            watcher_command(game.executable, game.install_dir),
            env=supervisor_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as error:
        # Without the supervisor the scale would never come back.
        if restore_monitor:
            display.apply(restore_monitor)
        raise HvrunnerError(f"{game.name} started, but the supervisor did not: {error}") from error


def launch(game: Game, config: dict[str, Any]) -> LaunchResult:
    prepared = plan(game, config, prepare=True)
    # Refused rather than started. Proton runs with "run" now, which would
    # happily put a second copy on top of the first, and two instances writing
    # the same saves is worse than a launch that declines.
    #
    # Asked of the process table, not of the wineserver socket: Proton keeps a
    # wineserver alive after the game exits, so the socket says "busy" for a
    # prefix whose game closed minutes ago and would block every later launch.
    if matching_game_pids(Path(game.executable).name, *game_roots(game.executable, game.install_dir)):
        raise HvrunnerError(f"{game.name} is already running")
    # Before the game rather than after: Wine holds the registry in wineserver
    # and flushes it on exit, so anything written while the game owns the prefix
    # is discarded the moment it quits. A prefix Proton has not built yet has no
    # system.reg to read, so nothing runs and the launch is not made to wait.
    # A native Linux game has no prefix and no Wine, so there is nothing here to
    # repair and no Proton build to repair it with.
    repairs = prefix_module.repair(prepared.prefix, resolve_proton(config, game)) if prepared.prefix else []
    log_path = new_log_path(game)
    restore_monitor = drop_to_native_scale(config)
    try:
        handle = log_path.open("w", buffering=1)
    except OSError as error:
        if restore_monitor:
            display.apply(restore_monitor)
        raise HvrunnerError(f"cannot open log {log_path}: {error}") from error
    try:
        for line in repairs:
            handle.write(f"# {line}\n")
        handle.write(f"$ {' '.join(prepared.command)}\n")
        # Child output goes to the log rather than the terminal the interface is
        # drawing on, which is what stops the interleaved output.
        process = subprocess.Popen(
            prepared.command,
            cwd=working_directory(game.executable),
            env=prepared.environment,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError as error:
        if restore_monitor:
            display.apply(restore_monitor)
        raise HvrunnerError(f"cannot start {game.name}: {error}") from error
    finally:
        # Popen duplicated the descriptor, so this copy is no longer needed.
        handle.close()

    _start_supervisor(game, config, restore_monitor)
    prune_logs()
    return LaunchResult(pid=process.pid, log_path=log_path)
