"""What a directory offers something that is picking a path.

Kept out of the interface so the rules about what gets listed, and where a
browse starts from, can be tested without a terminal.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .constants import WINDOWS_SUFFIXES

PARENT_NAME = ".."


class Want(Enum):
    """What the caller is asking the user to pick.

    EXECUTABLE means anything that can be launched, not only a Windows binary:
    a native Linux game's launcher has no extension at all and is recognised by
    its executable bit.
    """

    DIRECTORY = "directory"
    EXECUTABLE = "executable"


@dataclass(frozen=True)
class Entry:
    path: Path
    is_dir: bool
    size: int = 0
    is_parent: bool = False

    @property
    def name(self) -> str:
        if self.is_parent:
            return PARENT_NAME
        return f"{self.path.name}/" if self.is_dir else self.path.name


def windows_program(path: Path) -> bool:
    """Whether a path is something Proton can be asked to run.

    An installer has to be one. A native binary handed to Proton would be an ELF
    file passed to Wine, which cannot work and fails without saying why.
    """
    return path.suffix.casefold() in WINDOWS_SUFFIXES


def runnable(name: str, mode: int) -> bool:
    """Whether a file is something that could be launched.

    A Windows program by extension, or any regular file with the executable
    bit, which is what a native Linux build's launcher has instead of a suffix.
    """
    dot = name.rfind(".")
    if dot > 0 and name[dot:].casefold() in WINDOWS_SUFFIXES:
        return True
    return stat.S_ISREG(mode) and bool(mode & 0o111)


def launchable(path: Path) -> bool:
    """Whether a path names a file that could be launched.

    A Windows program by extension, or any file with the executable bit, which
    is what a native Linux build's launcher has instead of an extension.
    """
    try:
        return path.is_file() and runnable(path.name, path.stat().st_mode)
    except OSError:
        return False


def listing(directory: Path, want: Want) -> list[Entry]:
    """The parent, then directories, then whatever files apply, each by name.

    Hidden entries are skipped for the reason the library scan skips them: the
    Proton prefix lives inside the game folder and holds a whole Windows tree.

    os.scandir rather than iterdir, so telling a directory from a file costs
    nothing and the one stat a file does need also answers its size.
    """
    entries: list[Entry] = []
    if directory.parent != directory:
        entries.append(Entry(directory.parent, is_dir=True, is_parent=True))
    try:
        with os.scandir(directory) as scanner:
            children = sorted(scanner, key=lambda child: child.name.casefold())
    except OSError:
        # An unreadable directory still has to offer the way back out of it.
        return entries
    directories: list[Entry] = []
    files: list[Entry] = []
    for child in children:
        if child.name.startswith("."):
            continue
        try:
            if child.is_dir():
                directories.append(Entry(Path(child.path), is_dir=True))
                continue
            if want is Want.DIRECTORY:
                continue
            stats = child.stat()
            if runnable(child.name, stats.st_mode):
                files.append(Entry(Path(child.path), is_dir=False, size=stats.st_size))
        except OSError:
            continue
    return [*entries, *directories, *files]


def start_directory(text: str, fallback: Path) -> Path:
    """The deepest existing directory of what was typed.

    Typing most of a path and then asking for the browser should not throw that
    away, and a path that does not exist yet still names a folder that does.
    """
    candidate = Path(text).expanduser() if text.strip() else fallback
    while not candidate.is_dir():
        parent = candidate.parent
        if parent == candidate:
            # Climbed past the root without finding anything, which takes a
            # filesystem in a state no browse is going to improve.
            return Path.home()
        candidate = parent
    return candidate


def human_size(count: int) -> str:
    """A short size. The column is narrow and the exact byte count is not useful."""
    value = float(max(0, count))
    if value < 1024:
        return f"{value:.0f}B"
    for unit in ("K", "M", "G", "T"):
        value /= 1024
        if value < 1024:
            return f"{value:.1f}{unit}"
    return f"{value:.1f}P"
