"""Discovering games on disk."""

from __future__ import annotations

import os
import re
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .constants import (
    CUSTOM_SOURCE,
    EXE_SEARCH_DEPTH,
    INSTALLER_PATTERN,
    NATIVE_SEARCH_DEPTH,
    SUFFIX_RANK,
    WINDOWS_SUFFIXES,
)
from .models import Game, favorite_key


def display_name(folder: Path) -> str:
    """Humanise a folder name without destroying deliberate capitalisation.

    str.title() makes BFResynced into Bfresynced and Assassin's into Assassin'S,
    so only fully lowercase words are capitalised.
    """
    cleaned = re.sub(r"[._-]+", " ", folder.name).strip()
    if not cleaned:
        return folder.name
    words = [word.capitalize() if word.islower() else word for word in cleaned.split()]
    return " ".join(words) or folder.name


def _suffix(name: str) -> str:
    """The extension, folded, without building a Path to get it.

    This runs once per directory entry during a library scan, and constructing a
    Path per entry is the allocation the scandir rewrite exists to avoid.
    """
    dot = name.rfind(".")
    return name[dot:].casefold() if dot > 0 else ""


def collect_files(
    folder: Path,
    max_depth: int,
    keep: Callable[[os.DirEntry[str]], bool],
    skip: frozenset[str] = frozenset(),
) -> list[Path]:
    """Files below folder that keep accepts, descending at most max_depth levels.

    os.scandir rather than iterdir: the kernel hands back each entry's type with
    its name, so telling a file from a directory needs no stat. Measured across
    a real library at a tenth of the cost, for identical results. Hidden
    directories are skipped, which keeps the Proton prefix living inside the
    game folder from offering every Windows system binary.
    """
    found: list[Path] = []

    def walk(directory: str, depth: int) -> None:
        try:
            with os.scandir(directory) as scanner:
                entries = sorted(scanner, key=lambda entry: entry.name)
        except OSError:
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            try:
                if entry.is_file():
                    if keep(entry):
                        found.append(Path(entry.path))
                elif depth < max_depth and entry.is_dir() and entry.name.casefold() not in skip:
                    walk(entry.path, depth + 1)
            except OSError:
                continue

    walk(str(folder), 0)
    return found


# Extensions a native game ships beside its binary, all seen mode 755 in a real
# library folder.
NOT_PROGRAMS = frozenset({".so", ".pak", ".dat", ".bin", ".txt", ".html", ".json", ".md", ".log", ".ini", ".cfg"})


def _windows_program(entry: os.DirEntry[str]) -> bool:
    return _suffix(entry.name) in WINDOWS_SUFFIXES


def _native_program(entry: os.DirEntry[str]) -> bool:
    """An executable file that is not a Windows program.

    The executable bit is the only thing separating a Linux game's launcher from
    its data files, and reading it costs a stat, which is why this runs only for
    a folder that offered no Windows program at all.
    """
    suffix = _suffix(entry.name)
    if suffix in WINDOWS_SUFFIXES or suffix in NOT_PROGRAMS or ".so." in entry.name:
        return False
    try:
        mode = entry.stat().st_mode
        if not stat.S_ISREG(mode) or not mode & 0o111:
            return False
        with Path(entry.path).open("rb") as handle:
            head = handle.read(4)
    except OSError:
        return False
    # An Electron game ships every file mode 755, licences and .pak data
    # included, so the executable bit alone offers a folder full of candidates.
    # The first four bytes settle it: an ELF image or a script's shebang.
    return head[:4] == b"\x7fELF" or head[:2] == b"#!"


def executable_candidates(
    folder: Path,
    max_depth: int = EXE_SEARCH_DEPTH,
    skip: frozenset[str] = frozenset(),
) -> list[Path]:
    """Windows programs up to max_depth levels below folder."""
    return collect_files(folder, max_depth, _windows_program, skip)


def native_candidates(folder: Path, max_depth: int = NATIVE_SEARCH_DEPTH) -> list[Path]:
    """Native Linux programs near the top of folder.

    Shallow on purpose: a Linux build keeps its launcher at the top, and depth
    here only offers more of the game's own tooling.
    """
    return collect_files(folder, max_depth, _native_program)


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def rank_executables(executables: list[Path], base: Path, token: str) -> list[Path]:
    """Shallower, then name affinity, then kind, then alphabetical.

    File size is deliberately not a tiebreak: it would quietly prefer a larger
    sibling such as a _Plus.exe variant over the binary already in use.
    """

    def rank(path: Path) -> tuple[int, int, int, str]:
        stem = normalise(path.stem)
        if stem == token:
            name_score = 0
        elif token and (stem in token or token in stem):
            name_score = 1
        else:
            name_score = 2
        # Kind breaks a tie between equally named siblings only: a real game
        # ships an .exe, and a .bat or .msi beside it is a wrapper around one.
        kind = SUFFIX_RANK.get(path.suffix.casefold(), len(SUFFIX_RANK))
        return (len(path.relative_to(base).parts), name_score, kind, path.name.casefold())

    return sorted(executables, key=rank)


def select_executable(folder: Path) -> Path | None:
    """Pick the most plausible game binary rather than the alphabetical first.

    Windows programs first; a folder holding none is walked again, shallower,
    for a native build. That second walk is paid only by folders the scan would
    otherwise have dropped entirely.
    """
    executables = executable_candidates(folder) or native_candidates(folder)
    if not executables:
        return None
    playable = [path for path in executables if not INSTALLER_PATTERN.search(path.name)] or executables
    return rank_executables(playable, folder, normalise(folder.name))[0]


def _subdirectories(root: Path) -> list[Path]:
    try:
        with os.scandir(root) as scanner:
            names = sorted(entry.name for entry in scanner if entry.is_dir() and not entry.name.startswith("."))
    except OSError:
        return []
    return [root / name for name in names]


def _scanned_games(config: dict[str, Any], favorites: set[str], seen: set[str], claimed: set[str]) -> list[Game]:
    games: list[Game] = []
    for root_text in config["library_roots"]:
        root = Path(str(root_text)).expanduser()
        for folder in _subdirectories(root):
            # A declared entry claiming this folder has already been emitted.
            if str(folder) in claimed:
                continue
            executable = select_executable(folder)
            if executable is None or str(executable) in seen:
                continue
            seen.add(str(executable))
            claimed.add(str(folder))
            games.append(
                Game(
                    display_name(folder),
                    CUSTOM_SOURCE,
                    str(folder),
                    str(executable),
                    favorite=favorite_key(executable) in favorites,
                )
            )
    return games


def entry_install_dir(entry: dict[str, Any], executable: Path) -> Path:
    """Where the entry's prefix lives.

    An installed game's executable sits inside the prefix, so its parent is the
    wrong answer and the folder has to be stored.
    """
    declared = str(entry.get("install_dir") or "").strip()
    return Path(declared).expanduser() if declared else executable.parent


def game_folder(executable: Path, roots: list[Path]) -> Path:
    """The folder a hand-added executable belongs to.

    The scan gives a game the library subdirectory it was found in, and that is
    where its prefix lives. Adding the same binary by hand used to give it the
    binary's own folder instead, so a nested executable got a second prefix one
    level down, holding none of the saves the first one had.
    """
    for root in roots:
        try:
            relative = executable.relative_to(root)
        except ValueError:
            continue
        if len(relative.parts) > 1:
            return root / relative.parts[0]
    return executable.parent


def entry_env(entry: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Per game environment as pairs, ignoring anything that is not a mapping."""
    values = entry.get("env")
    if not isinstance(values, dict):
        return ()
    return tuple((str(name), str(value)) for name, value in values.items())


def _declared_games(config: dict[str, Any], favorites: set[str], seen: set[str], claimed: set[str]) -> list[Game]:
    games: list[Game] = []
    for entry in config["custom_games"]:
        if not isinstance(entry, dict):
            continue
        executable = Path(str(entry.get("executable", ""))).expanduser()
        if not executable.is_file():
            continue
        install_dir = entry_install_dir(entry, executable)
        # The executable is the only thing that makes two declared entries
        # distinct, so it is the only dedupe key here: one folder legitimately
        # holds a game and its mod loader. Claiming the folder is a separate
        # matter, and only the scan consults it.
        if str(executable) in seen:
            continue
        seen.add(str(executable))
        claimed.add(str(install_dir))
        raw_args = entry.get("launch_args", [])
        arguments = tuple(str(arg) for arg in raw_args if isinstance(arg, str)) if isinstance(raw_args, list) else ()
        games.append(
            Game(
                str(entry.get("name") or display_name(install_dir)),
                CUSTOM_SOURCE,
                str(install_dir),
                str(executable),
                steam_appid=str(entry.get("steam_appid", "")).strip(),
                proton_path=str(entry.get("proton_path", "")).strip(),
                launch_args=arguments,
                env=entry_env(entry),
                favorite=favorite_key(executable) in favorites,
            )
        )
    return games


def custom_games(config: dict[str, Any], favorites: set[str]) -> list[Game]:
    # Declared first: they exist to override what the scan would otherwise find.
    seen: set[str] = set()
    claimed: set[str] = set()
    declared = _declared_games(config, favorites, seen, claimed)
    return declared + _scanned_games(config, favorites, seen, claimed)


def sort_games(games: list[Game]) -> list[Game]:
    """Favourites first, then by name.

    One definition, because toggling a favourite re-sorts what is already in
    memory rather than walking every library folder again for one boolean.
    """
    return sorted(games, key=lambda game: (not game.favorite, game.name.casefold(), game.source))


def library(config: dict[str, Any]) -> list[Game]:
    favorites = {str(item) for item in config["favorites"]}
    return sort_games(custom_games(config, favorites))
