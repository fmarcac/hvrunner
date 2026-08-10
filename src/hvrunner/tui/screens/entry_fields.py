"""What an entry's fields are, and what changing each one does.

Separate from the screen that presents them, the same way settings_entries is
separate from settings: this module knows the entry, the screen knows the
layout.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ...core.browsing import Want
from ...core.config import expand

if TYPE_CHECKING:
    from .entry import EntryScreen


@dataclass
class Field:
    label: str
    detail: str
    value: Callable[[], str]
    activate: Callable[[], None]


def _edit_text(screen: EntryScreen, key: str, label: str) -> Callable[[], None]:
    def action() -> None:
        entered = screen.app.prompt(label, str(screen.entry.get(key, "")))
        if not entered:
            # Cancelled, or cleared. A nameless entry is not worth storing.
            return
        screen.set_field(key, entered)

    return action


def _edit_path(screen: EntryScreen, key: str, label: str, want: Want) -> Callable[[], None]:
    def action() -> None:
        entered = screen.app.prompt_path(label, want, str(screen.entry.get(key, "")))
        if entered is None:
            return
        if not entered:
            # Cleared. expand("") is ".", so this must never reach expand. An
            # entry with no executable is not an entry, but an empty install
            # folder is meaningful: entry_install_dir falls back to the folder
            # the executable is in.
            if key == "executable":
                return
            screen.set_field(key, "")
            return
        resolved = expand(entered)
        if key == "executable" and not Path(resolved).is_file():
            screen.app.status = f"No readable file at {resolved}"
            return
        screen.set_field(key, resolved)

    return action


def clean_steam_appid(value: str) -> str | None:
    """The id as it should be stored, or None when it is not usable.

    Digits only. umu builds GAMEID as umu-<id> and matches it against
    ^umu-[\\d\\w]+$, so anything else either fails that check or reaches Steam
    as nonsense, and in both cases the launch runs as application 0 without
    saying so.
    """
    cleaned = value.strip()
    return cleaned if cleaned == "" or cleaned.isdigit() else None


def _edit_steam_appid(screen: EntryScreen) -> Callable[[], None]:
    def action() -> None:
        entered = screen.app.prompt("Steam app id, blank for none", str(screen.entry.get("steam_appid", "")))
        if entered is None:
            return
        cleaned = clean_steam_appid(entered)
        if cleaned is None:
            screen.app.status = f"A Steam app id is digits only: {entered}"
            return
        screen.set_field("steam_appid", cleaned)

    return action


def _edit_args(screen: EntryScreen) -> Callable[[], None]:
    def action() -> None:
        current = " ".join(str(item) for item in screen.entry.get("launch_args", []))
        entered = screen.app.prompt("Launch arguments, space separated", current)
        if entered is None:
            return
        screen.set_field("launch_args", entered.split())

    return action


def build(screen: EntryScreen) -> list[Field]:
    entry = screen.entry
    return [
        Field(
            "Name",
            "What the library shows. Only this entry is affected.",
            lambda: str(entry.get("name", "")),
            _edit_text(screen, "name", "Name it"),
        ),
        Field(
            "Executable",
            "The binary that runs. Changing it moves the favourite with it, "
            "because the favourite key is built from this path.",
            lambda: str(entry.get("executable", "")),
            _edit_path(screen, "executable", "Path to a Windows executable", Want.EXECUTABLE),
        ),
        Field(
            "Steam app id",
            "Runs the game under this Steam application id and turns on Proton's "
            "Steam bridge. 480 is Spacewar, the id used for anything that is not "
            "a Steam game. Blank runs under no id at all.",
            lambda: str(entry.get("steam_appid", "")) or "none",
            _edit_steam_appid(screen),
        ),
        Field(
            "Install folder",
            "Where the Proton prefix lives. For a game installed by an installer "
            "this is the game folder, not the folder holding the executable.",
            lambda: str(entry.get("install_dir", "")),
            _edit_path(screen, "install_dir", "Folder holding the prefix", Want.DIRECTORY),
        ),
        Field(
            "Launch arguments",
            "Passed to the executable after the umu command.",
            lambda: " ".join(str(item) for item in entry.get("launch_args", [])) or "none",
            _edit_args(screen),
        ),
    ]
