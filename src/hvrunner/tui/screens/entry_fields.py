"""What an entry's fields are, and what changing each one does.

Separate from the screen that presents them, the same way settings_entries is
separate from settings: this module knows the entry, the screen knows the
layout.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from ...core.browsing import Want
from ...core.config import expand
from ..options import Option

if TYPE_CHECKING:
    from .entry import EntryScreen


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

    Digits only. It reaches Steam as SteamAppId and protonfixes as the game id,
    and anything that is not a number is either ignored or read as zero, in both
    cases without saying so.
    """
    cleaned = value.strip()
    return cleaned if cleaned == "" or cleaned.isdigit() else None


def parse_env(text: str) -> dict[str, str] | None:
    """NAME=VALUE pairs, or None when one of them is not a pair.

    Space separated, because the field is a single line. A value with a space in
    it belongs in extra_env in the config file instead; nothing the Windows side
    is configured with needs one.
    """
    values: dict[str, str] = {}
    for item in text.split():
        name, separator, value = item.partition("=")
        if not separator or not name:
            return None
        values[name] = value
    return values


def format_env(values: object) -> str:
    if not isinstance(values, dict) or not values:
        return ""
    return " ".join(f"{name}={value}" for name, value in values.items())


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


def _edit_env(screen: EntryScreen) -> Callable[[], None]:
    def action() -> None:
        entered = screen.app.prompt("Environment, NAME=VALUE pairs", format_env(screen.entry.get("env")))
        if entered is None:
            return
        parsed = parse_env(entered)
        if parsed is None:
            screen.app.status = f"Environment is NAME=VALUE pairs: {entered}"
            return
        screen.set_field("env", parsed)

    return action


def build(screen: EntryScreen) -> list[Option]:
    entry = screen.entry
    return [
        Option(
            "Name",
            "What the library shows. Only this entry is affected.",
            lambda: str(entry.get("name", "")),
            _edit_text(screen, "name", "Name it"),
        ),
        Option(
            "Executable",
            "The binary that runs. A Windows program goes through Proton and "
            "anything else is started directly. Changing this moves the "
            "favourite with it, because the favourite key is built from it.",
            lambda: str(entry.get("executable", "")),
            _edit_path(screen, "executable", "Path to a game executable", Want.EXECUTABLE),
        ),
        Option(
            "Steam app id",
            "Runs the game under this Steam application id and turns on Proton's "
            "Steam bridge. 480 is Spacewar, the id used for anything that is not "
            "a Steam game. Blank lets hvrunner work it out.",
            lambda: str(entry.get("steam_appid", "")) or "none",
            _edit_steam_appid(screen),
        ),
        Option(
            "Install folder",
            "Where the Proton prefix lives. For a game installed by an installer "
            "this is the game folder, not the folder holding the executable.",
            lambda: str(entry.get("install_dir", "")),
            _edit_path(screen, "install_dir", "Folder holding the prefix", Want.DIRECTORY),
        ),
        Option(
            "Proton build",
            "A Proton build for this game alone, overriding the configured one. "
            "Wine features differ between builds: a game whose plugin wants a "
            "WinRT class one build does not implement needs another. Blank uses "
            "the configured build.",
            lambda: str(entry.get("proton_path", "")) or "configured",
            _edit_path(screen, "proton_path", "Path to a Proton build", Want.DIRECTORY),
        ),
        Option(
            "Launch arguments",
            "Passed to the executable after the Proton command.",
            lambda: " ".join(str(item) for item in entry.get("launch_args", [])) or "none",
            _edit_args(screen),
        ),
        Option(
            "Environment",
            "NAME=VALUE pairs for this game alone, applied after everything "
            "else so they win. This is where a DXVK or NVAPI workaround for one "
            "title belongs, rather than in the package.",
            lambda: format_env(entry.get("env")) or "none",
            _edit_env(screen),
        ),
    ]
