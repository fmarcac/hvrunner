"""Per launch log capture and incremental reading.

Child output used to go straight to the terminal the curses UI was drawing on,
which is what produced interleaved, half overwritten lines. Everything a game
and its helpers emit now lands in a file here instead, and the UI reads it back
as a normal scrollable feed.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from .constants import LOG_KEEP, LOG_TAIL_BYTES, log_dir
from .models import Game, HvrunnerError

# CSI sequences, plus the OSC title-setting form some Wine helpers emit.
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_line(text: str) -> str:
    """Strip escape sequences and honour carriage returns.

    A progress line ending in \\r overwrites itself; keeping only the final
    segment is what the terminal would have shown.
    """
    text = text.replace("\r\n", "\n")
    if "\r" in text:
        text = text.split("\r")[-1]
    text = _ANSI.sub("", text)
    return _CONTROL.sub("", text).rstrip()


# Messages already diagnosed as expected on this setup. The interface dims them
# so a real failure is not lost in the middle of them.
NOISE_PATTERNS = (
    "libgamemode.so",
    "gamemodeauto:",
    "playerctld",
    "is blacklisted in MangoHud",
    "Spoofing CPUID",
    "XI_BadDevice",
)

_ERROR_HINT = re.compile(r"\b(error|failed|failure|fatal|abort|cannot)\b", re.I)
_WARNING_HINT = re.compile(r"\b(warn|warning|deprecated)\b", re.I)


def classify(line: str) -> str:
    """Sort a log line into command, noise, error, warning or plain.

    Noise is checked before error on purpose: the expected gamemode message
    contains "cannot open shared object file" and would otherwise read as a
    failure.
    """
    if line.startswith("$ "):
        return "command"
    lowered = line.casefold()
    if any(pattern.casefold() in lowered for pattern in NOISE_PATTERNS):
        return "noise"
    if _ERROR_HINT.search(line):
        return "error"
    if _WARNING_HINT.search(line):
        return "warning"
    return "plain"


def new_log_path(game: Game, now: float | None = None) -> Path:
    directory = log_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise HvrunnerError(f"cannot create log directory {directory}: {error}") from error
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now if now is not None else time.time()))
    return directory / f"{stamp}-{game.slug}.log"


def prune_logs(keep: int = LOG_KEEP) -> None:
    directory = log_dir()
    try:
        files = sorted((path for path in directory.glob("*.log") if path.is_file()), reverse=True)
    except OSError:
        return
    for path in files[keep:]:
        path.unlink(missing_ok=True)


def recent_logs(limit: int = LOG_KEEP) -> list[Path]:
    try:
        return sorted((path for path in log_dir().glob("*.log") if path.is_file()), reverse=True)[:limit]
    except OSError:
        return []


class LogReader:
    """Reads a growing log file incrementally, newest content last."""

    def __init__(self, path: Path, tail_bytes: int = LOG_TAIL_BYTES):
        self.path = path
        self.tail_bytes = tail_bytes
        self.lines: list[str] = []
        self._offset = 0
        self._partial = ""
        self._drop_fragment = False

    def poll(self) -> bool:
        """Append any new lines. Returns True when something was added."""
        try:
            size = self.path.stat().st_size
        except OSError:
            return False
        if size < self._offset:
            # Truncated or replaced, so start over.
            self._offset = 0
            self._partial = ""
            self._drop_fragment = False
            self.lines.clear()
        if self._offset == 0 and size > self.tail_bytes:
            self._offset = size - self.tail_bytes
            # That seek lands mid line, so the first piece read is the tail of a
            # line whose start was skipped. Showing it would be misleading.
            self._drop_fragment = True
        if size == self._offset:
            return False
        try:
            with self.path.open("rb") as handle:
                handle.seek(self._offset)
                chunk = handle.read(size - self._offset)
                self._offset = handle.tell()
        except OSError:
            return False
        text = self._partial + chunk.decode("utf-8", errors="replace")
        parts = text.split("\n")
        self._partial = parts.pop()
        if self._drop_fragment:
            self._drop_fragment = False
            if parts:
                parts.pop(0)
        added = False
        for raw in parts:
            cleaned = clean_line(raw)
            if cleaned:
                self.lines.append(cleaned)
                added = True
        return added
