"""Discovering games on disk."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .constants import CUSTOM_SOURCE, EXE_SEARCH_DEPTH, INSTALLER_PATTERN
from .models import Game, favorite_key


def display_name(folder: Path) -> str:
    """Humanise a folder name without destroying deliberate capitalisation.

    str.title() would turn BFResynced into Bfresynced and Assassin's into
    Assassin'S, so only fully lowercase words are capitalised.
    """
    cleaned = re.sub(r"[._-]+", " ", folder.name).strip()
    if not cleaned:
        return folder.name
    words = [word.capitalize() if word.islower() else word for word in cleaned.split()]
    return " ".join(words) or folder.name


def executable_candidates(folder: Path, max_depth: int = EXE_SEARCH_DEPTH) -> list[Path]:
    """Collect .exe files up to max_depth below folder.

    Hidden directories are skipped, which keeps the Proton prefix living inside
    the game folder from contributing every Windows system binary.
    """
    found: list[Path] = []

    def walk(directory: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            try:
                if entry.is_file():
                    if entry.suffix.lower() == ".exe":
                        found.append(entry)
                elif entry.is_dir():
                    walk(entry, depth + 1)
            except OSError:
                continue

    walk(folder, 0)
    return found


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def select_executable(folder: Path) -> Path | None:
    """Pick the most plausible game binary rather than the alphabetical first."""
    executables = executable_candidates(folder)
    if not executables:
        return None
    playable = [path for path in executables if not INSTALLER_PATTERN.search(path.name)] or executables
    folder_token = _normalise(folder.name)

    def rank(path: Path) -> tuple[int, int, str]:
        stem = _normalise(path.stem)
        if stem == folder_token:
            name_score = 0
        elif folder_token and (stem in folder_token or folder_token in stem):
            name_score = 1
        else:
            name_score = 2
        # Shallower, then name affinity, then alphabetical. File size is
        # deliberately not a tiebreak: it would quietly prefer a larger sibling
        # such as a _Plus.exe variant over the binary already in use.
        return (len(path.relative_to(folder).parts), name_score, path.name.casefold())

    return sorted(playable, key=rank)[0]


def _scanned_games(config: dict[str, Any], favorites: set[str], seen: set[str]) -> list[Game]:
    games: list[Game] = []
    for root_text in config["library_roots"]:
        root = Path(str(root_text)).expanduser()
        if not root.is_dir():
            continue
        try:
            folders = sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith("."))
        except OSError:
            continue
        for folder in folders:
            executable = select_executable(folder)
            if executable is None or str(executable) in seen:
                continue
            seen.add(str(executable))
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


def _declared_games(config: dict[str, Any], favorites: set[str], seen: set[str]) -> list[Game]:
    games: list[Game] = []
    for entry in config["custom_games"]:
        if not isinstance(entry, dict):
            continue
        executable = Path(str(entry.get("executable", ""))).expanduser()
        if not executable.is_file() or str(executable) in seen:
            continue
        seen.add(str(executable))
        raw_args = entry.get("launch_args", [])
        arguments = tuple(str(arg) for arg in raw_args if isinstance(arg, str)) if isinstance(raw_args, list) else ()
        games.append(
            Game(
                str(entry.get("name") or display_name(executable.parent)),
                CUSTOM_SOURCE,
                str(executable.parent),
                str(executable),
                launch_args=arguments,
                favorite=favorite_key(executable) in favorites,
            )
        )
    return games


def custom_games(config: dict[str, Any], favorites: set[str]) -> list[Game]:
    seen: set[str] = set()
    return _scanned_games(config, favorites, seen) + _declared_games(config, favorites, seen)


def library(config: dict[str, Any]) -> list[Game]:
    favorites = {str(item) for item in config["favorites"]}
    games = custom_games(config, favorites)
    return sorted(games, key=lambda game: (not game.favorite, game.name.casefold(), game.source))
