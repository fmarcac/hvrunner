"""What a directory offers something that is picking a path.

Kept out of the interface so the rules about what gets listed, and where a
browse starts from, can be tested without a terminal.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

PARENT_NAME = ".."


class Want(Enum):
    """What the caller is asking the user to pick.

    FILE rather than EXECUTABLE exists because not everything chosen here is a
    Windows binary: umu-run has no extension at all.
    """

    DIRECTORY = "directory"
    EXECUTABLE = "executable"
    FILE = "file"


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


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _wanted(path: Path, want: Want) -> bool:
    if want is Want.DIRECTORY:
        return False
    if want is Want.EXECUTABLE:
        return path.suffix.casefold() == ".exe"
    return True


def listing(directory: Path, want: Want) -> list[Entry]:
    """The parent, then directories, then whatever files apply, each by name.

    Hidden entries are skipped for the reason the library scan skips them: the
    Proton prefix lives inside the game folder and holds a whole Windows tree.
    """
    entries: list[Entry] = []
    if directory.parent != directory:
        entries.append(Entry(directory.parent, is_dir=True, is_parent=True))
    try:
        children = sorted(directory.iterdir(), key=lambda path: path.name.casefold())
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
                directories.append(Entry(child, is_dir=True))
            elif _wanted(child, want):
                files.append(Entry(child, is_dir=False, size=_size(child)))
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
