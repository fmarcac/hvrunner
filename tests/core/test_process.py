"""core.process exists for one reason, and this is it.

cli.main sets SIGCHLD to SIG_IGN so a launched game never becomes a zombie. The
kernel then reaps helper processes before subprocess can wait for them, and
Popen records status 0 for every one of them however it exited.
"""

from __future__ import annotations

import signal
import subprocess
import time
from pathlib import Path

import pytest

from hvrunner.core import process


@pytest.fixture
def ignoring_children():
    """What cli.main does to the process, put back afterwards."""
    previous = signal.getsignal(signal.SIGCHLD)
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)
    yield
    signal.signal(signal.SIGCHLD, previous)


def test_subprocess_alone_cannot_see_a_failure(ignoring_children):
    """The bug, pinned, so nobody has to be talked into believing it."""
    assert subprocess.run(["sh", "-c", "exit 3"], capture_output=True).returncode == 0


def test_the_real_exit_code_is_reported(ignoring_children):
    finished = process.run(["sh", "-c", "exit 3"], timeout=10)
    assert finished is not None
    assert finished.returncode == 3


def test_output_is_captured_rather_than_written_to_the_terminal(ignoring_children):
    finished = process.run(["sh", "-c", "echo out; echo bad >&2"], timeout=10)
    assert finished is not None
    assert finished.stdout.strip() == "out"
    assert finished.stderr.strip() == "bad"


def test_a_binary_that_cannot_be_run_is_none_rather_than_a_raise(ignoring_children):
    assert process.run(["/nonexistent/hvrunner-should-not-exist"], timeout=10) is None


def test_a_timeout_is_none_rather_than_a_raise(ignoring_children):
    assert process.run(["sh", "-c", "sleep 5"], timeout=0.2) is None


def test_nothing_that_exits_during_the_call_is_left_a_zombie(ignoring_children):
    """Restoring the default disposition is what makes the exit code readable.

    It is also what would strand a game that happened to exit while it was in
    force, which is why the window ends with an explicit drain.
    """
    child = subprocess.Popen(["sh", "-c", "sleep 0.1"])
    process.run(["sh", "-c", "sleep 0.5"], timeout=10)
    assert not Path(f"/proc/{child.pid}").exists()


def test_the_disposition_is_restored(ignoring_children):
    process.run(["sh", "-c", "exit 0"], timeout=10)
    assert signal.getsignal(signal.SIGCHLD) is signal.SIG_IGN


def test_without_sig_ign_nothing_is_touched():
    previous = signal.getsignal(signal.SIGCHLD)
    finished = process.run(["sh", "-c", "exit 7"], timeout=10)
    assert finished is not None and finished.returncode == 7
    assert signal.getsignal(signal.SIGCHLD) is previous


def test_a_helper_runs_where_it_is_told(tmp_path, ignoring_children):
    finished = process.run(["sh", "-c", "pwd"], timeout=10, cwd=tmp_path)
    assert finished is not None
    assert finished.stdout.strip() == str(tmp_path)
    # Nothing here should depend on wall clock, but the drain does run.
    assert time.monotonic() > 0
