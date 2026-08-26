"""Running a helper process and getting a truthful exit status.

cli.main sets SIGCHLD to SIG_IGN so a launched game never becomes a zombie, and
that has a consequence nothing here can opt out of: the kernel reaps children
before subprocess can wait for them, so Popen records status 0 for every child
however it actually exited. A failed `wine reg add` and a failed `hyprctl` both
looked like successes, and the launch log said so.

Restoring the default disposition for the length of one synchronous call is what
makes the return code mean something again. Anything that dies during that
window would be left a zombie, so the window is closed by draining explicitly
rather than by hoping SIG_IGN collects what it did not see.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
from collections.abc import Iterator
from pathlib import Path


def _drain() -> None:
    """Reap whatever exited while the default disposition was in force."""
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except (ChildProcessError, OSError):
            return
        if pid == 0:
            return


@contextlib.contextmanager
def truthful_exit_status() -> Iterator[None]:
    """Make the next child's return code readable, then put SIGCHLD back."""
    try:
        previous = signal.getsignal(signal.SIGCHLD)
    except (AttributeError, ValueError):
        yield
        return
    if previous is not signal.SIG_IGN:
        # Nothing is discarding statuses, so there is nothing to work around.
        yield
        return
    try:
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    except (OSError, ValueError):
        # Not the main thread. Better a doubtful status than a broken handler.
        yield
        return
    try:
        yield
    finally:
        with contextlib.suppress(OSError, ValueError):
            signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        _drain()


def run(
    command: list[str],
    *,
    timeout: float,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str] | None:
    """Run a helper to completion. None means it could not be run at all.

    Output is captured rather than inherited: everything here runs while curses
    owns the terminal, and a helper writing to it produces the interleaved,
    half overwritten lines the log file exists to prevent.
    """
    try:
        with truthful_exit_status():
            return subprocess.run(
                command,
                env=env,
                cwd=str(cwd) if cwd is not None else None,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
    except (OSError, subprocess.SubprocessError):
        return None
