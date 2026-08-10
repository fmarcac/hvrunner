"""Keeping a launched game spread across every CPU."""

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


def watcher_command(executable_name: str, install_dir: str) -> list[str]:
    """Build the argv that re-enters this package in watcher mode."""
    installed = shutil.which("hvrunner")
    if installed:
        return [installed, "--affinity-watch", executable_name, install_dir]
    shim = Path(__file__).resolve().parents[2] / "bin" / "hvrunner"
    return [sys.executable, str(shim), "--affinity-watch", executable_name, install_dir]


def matching_game_pids(executable_name: str, install_dir: str) -> list[int]:
    expected_comm = executable_name[:COMM_MAX_LENGTH]
    try:
        expected_cwd = Path(install_dir).resolve()
    except OSError:
        return []
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return []
    matches: list[int] = []
    for process_dir in entries:
        if not process_dir.name.isdigit():
            continue
        try:
            comm = (process_dir / "comm").read_text().strip()
            cwd = (process_dir / "cwd").resolve()
        except OSError:
            # FileNotFoundError and PermissionError are both OSError subclasses.
            continue
        if comm == expected_comm and cwd == expected_cwd:
            matches.append(int(process_dir.name))
    return matches


def set_full_affinity(pid: int, cpus: set[int]) -> None:
    try:
        thread_ids = [int(path.name) for path in Path(f"/proc/{pid}/task").iterdir() if path.name.isdigit()]
    except OSError:
        return
    for thread_id in thread_ids:
        try:
            if os.sched_getaffinity(thread_id) != cpus:
                os.sched_setaffinity(thread_id, cpus)
        except OSError:
            # Thread exited, or the mask is not permitted.
            continue


def supervise(executable_name: str, install_dir: str) -> None:
    """Follow a game for its lifetime, then undo what launching it changed.

    This process outlives the launcher, so it is the only thing that reliably
    knows when the game is gone. Restoring the output scale has to happen here.
    """
    enforce = os.environ.get(ENFORCE_AFFINITY_ENV, "1") != "0"
    restore = os.environ.get(RESTORE_MONITOR_ENV)
    try:
        affinity_watch(executable_name, install_dir, enforce=enforce)
    finally:
        if restore:
            display.apply(restore)


def affinity_watch(executable_name: str, install_dir: str, *, enforce: bool = True) -> None:
    cpus = all_cpus()
    startup_deadline = time.monotonic() + AFFINITY_STARTUP_TIMEOUT
    missing_since: float | None = None
    game_seen = False
    while True:
        matches = matching_game_pids(executable_name, install_dir)
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
        time.sleep(AFFINITY_POLL_INTERVAL)
