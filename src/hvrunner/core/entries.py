"""Creating, changing and removing the entries declared in the config.

Pure dictionary work: no curses, and no disk access beyond the config the
caller owns. That is what makes the favourite migration testable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import Game, favorite_key


def draft(game: Game) -> dict[str, Any]:
    """The entry a scanned game would become, without writing anything."""
    return {
        "name": game.name,
        "executable": game.executable,
        "install_dir": game.install_dir,
        "launch_args": list(game.launch_args),
    }


def find(config: dict[str, Any], executable: str) -> dict[str, Any] | None:
    """Match on the expanded path.

    library expands an entry before it reaches Game.executable, but load_config
    leaves custom_games exactly as written, so a hand written "~/games/x.exe"
    would never match the game built from it.
    """
    wanted = Path(str(executable)).expanduser()
    for entry in config["custom_games"]:
        if isinstance(entry, dict) and Path(str(entry.get("executable", ""))).expanduser() == wanted:
            return entry
    return None


def add(config: dict[str, Any], entry: dict[str, Any]) -> None:
    config["custom_games"].append(dict(entry))


def update(config: dict[str, Any], original_executable: str, entry: dict[str, Any]) -> None:
    """Replace the entry for original_executable, or add it when absent.

    Adding is the promotion case: a scanned game has nothing stored yet.
    """
    existing = find(config, original_executable)
    if existing is None:
        add(config, entry)
    else:
        existing.clear()
        existing.update(entry)
    _move_favorite(config, original_executable, str(entry["executable"]))


def remove(config: dict[str, Any], executable: str) -> bool:
    """Drop the entry and any favourite pointing at it."""
    existing = find(config, executable)
    if existing is None:
        return False
    config["custom_games"].remove(existing)
    stale = favorite_key(executable)
    config["favorites"] = [item for item in config["favorites"] if str(item) != stale]
    return True


def _move_favorite(config: dict[str, Any], old_executable: str, new_executable: str) -> None:
    """Follow the favourite when the executable changes.

    Game.key is built from the executable, so without this the favourite would
    silently stop matching after an edit. Both keys come from favorite_key so
    they cannot drift from Game.key.
    """
    if str(old_executable) == str(new_executable):
        return
    stale = favorite_key(old_executable)
    favorites = [str(item) for item in config["favorites"]]
    if stale not in favorites:
        return
    kept = [item for item in favorites if item != stale]
    config["favorites"] = sorted({*kept, favorite_key(new_executable)})
