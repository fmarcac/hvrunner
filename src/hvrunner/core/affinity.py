"""Keeping a launched game spread across every CPU.

This runs in a process that outlives the interface, for as long as the game
does, so what it costs per pass is what it costs the game. The scan walks every
process on the machine, which is why the cheap test comes first and why the
interval opens out once the game has been found.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

from . import display
from .constants import (
    AFFINITY_ABSENCE_TIMEOUT,
    AFFINITY_POLL_INTERVAL,
    AFFINITY_SETTLED_INTERVAL,
    AFFINITY_STARTUP_TIMEOUT,
    COMM_MAX_LENGTH,
    ENFORCE_AFFINITY_ENV,
    RESTORE_MONITOR_ENV,
)


def all_cpus() -> set[int]:
    """Every CPU on the machine, independent of the caller's own mask.

    Reading sched_getaffinity(0) here would propagate a restricted mask from
    whatever started the UI, which is the opposite of what enforce_all_cpus
    is for.
    """
    return set(range(os.cpu_count() or 1))


def watcher_command(executable: str, install_dir: str) -> list[str]:
    """Build the argv that re-enters this package in watcher mode.

    The whole executable path, not just its name: the watcher needs the folder
    the game was started in as well as the folder the prefix lives in, and it
    can derive both from this without a third argument.
    """
    installed = shutil.which("hvrunner")
    if installed:
        return [installed, "--affinity-watch", executable, install_dir]
    shim = Path(__file__).resolve().parents[2] / "bin" / "hvrunner"
    return [sys.executable, str(shim), "--affinity-watch", executable, install_dir]


def game_roots(executable: str, install_dir: str) -> tuple[str, ...]:
    """The directories a running copy of this game may report as its cwd.

    Both, because they are not always the same one: launcher starts a game in
    the folder its binary is in, which is a level below install_dir whenever the
    binary is nested, as Hitman's is in "Hitman Absolution/HMA.exe".
    """
    return (install_dir, str(Path(executable).parent))


def matching_game_pids(executable_name: str, *roots: str) -> list[int]:
    """Pids whose comm is this executable and whose cwd is inside one of roots.

    Inside, not equal to. Comparing against install_dir alone matched nothing
    for a game whose binary is nested, because that is not the folder the game
    was started in: affinity enforcement quietly did nothing, the already
    running guard never fired, and the supervisor sat out its whole startup
    timeout before restoring the output scale in the middle of the game.
    Containment also covers a game that chdirs into a subfolder of its own.

    comm is read before cwd is resolved, because comm rules out every process
    but a handful and cwd is the expensive half. os.readlink rather than
    Path.resolve: the kernel has already resolved that link, and resolving it
    again walks the whole path a second time. Together those took the scan from
    17 ms to under 5, which matters because it runs for as long as the game does.
    """
    expected_comm = executable_name[:COMM_MAX_LENGTH].encode()
    resolved: list[str] = []
    for root in roots:
        try:
            resolved.append(os.path.realpath(root))
        except OSError:
            continue
    if not resolved:
        return []
    contained = tuple(root.rstrip("/") + "/" for root in resolved)
    try:
        with os.scandir("/proc") as scanner:
            names = [entry.name for entry in scanner if entry.name.isdigit()]
    except OSError:
        return []
    matches: list[int] = []
    for name in names:
        try:
            with open(f"/proc/{name}/comm", "rb") as handle:
                if handle.read(COMM_MAX_LENGTH + 2).strip() != expected_comm:
                    continue
            cwd = os.readlink(f"/proc/{name}/cwd")
        except OSError:
            # FileNotFoundError and PermissionError are both OSError subclasses.
            continue
        if cwd in resolved or cwd.startswith(contained):
            matches.append(int(name))
    return matches


def set_full_affinity(pid: int, cpus: set[int]) -> None:
    try:
        thread_names = os.listdir(f"/proc/{pid}/task")
    except OSError:
        return
    for name in thread_names:
        try:
            thread_id = int(name)
            if os.sched_getaffinity(thread_id) != cpus:
                os.sched_setaffinity(thread_id, cpus)
        except (OSError, ValueError):
            # Thread exited, or the mask is not permitted.
            continue


def supervise(executable: str, install_dir: str) -> None:
    """Follow a game for its lifetime, then undo what launching it changed.

    This process outlives the launcher, so it is the only thing that reliably
    knows when the game is gone. Restoring the output scale has to happen here.
    """
    enforce = os.environ.get(ENFORCE_AFFINITY_ENV, "1") != "0"
    restore = os.environ.get(RESTORE_MONITOR_ENV)
    try:
        affinity_watch(executable, install_dir, enforce=enforce)
    finally:
        if restore:
            display.apply(restore)


def affinity_watch(executable: str, install_dir: str, *, enforce: bool = True) -> None:
    name = Path(executable).name
    roots = game_roots(executable, install_dir)
    cpus = all_cpus()
    startup_deadline = time.monotonic() + AFFINITY_STARTUP_TIMEOUT
    missing_since: float | None = None
    game_seen = False
    while True:
        matches = matching_game_pids(name, *roots)
        now = time.monotonic()
        if matches:
            game_seen = True
            missing_since = None
            if enforce:
                for pid in matches:
                    set_full_affinity(pid, cpus)
        elif not game_seen:
            if now >= startup_deadline:
                return
        elif missing_since is None:
            missing_since = now
        elif now - missing_since >= AFFINITY_ABSENCE_TIMEOUT:
            return
        # Tight only while waiting for the game to appear. After that the scan
        # is watching for a mask the game sets on itself and for the exit, and
        # neither is worth walking every process four times a second for.
        time.sleep(AFFINITY_POLL_INTERVAL if not game_seen else AFFINITY_SETTLED_INTERVAL)
