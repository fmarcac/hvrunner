"""Application shell.

Holds the state the screens read and the actions they invoke. Drawing and key
handling live in the individual screens.
"""

from __future__ import annotations

import curses
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ..core import entries, installer
from ..core.browsing import Want, launchable, windows_program
from ..core.config import expand, save_config, unknown_keys
from ..core.constants import LAUNCH_SETTLE_SECONDS, SPACEWAR_APPID
from ..core.launcher import alive, launch
from ..core.library import display_name, game_folder, library, sort_games
from ..core.models import Game, HvrunnerError
from . import prompt as prompt_module
from .paths import ask_for_path
from .screens import (
    EntryScreen,
    HelpScreen,
    LibraryScreen,
    LogScreen,
    PickerScreen,
    SettingsScreen,
)
from .theme import Theme
from .widgets import Painter


@dataclass(frozen=True)
class Watch:
    """A launch whose process is still being followed."""

    name: str
    pid: int
    started: float


class App:
    def __init__(self, screen: Any, config: dict[str, Any], path: Path):
        self.screen = screen
        self.config = config
        self.path = path
        self.theme = Theme()
        self.theme.setup()
        self.paint = Painter(screen, self.theme)
        self.games = library(config)
        self.selected = 0
        unknown = unknown_keys(config)
        # Kept in the file either way, so this is the only sign a key is a typo.
        self.status = f"Not a setting, kept but ignored: {', '.join(unknown)}" if unknown else ""
        self.active_log: Path | None = None
        self.watching: Watch | None = None
        curses.curs_set(0)
        self.screen.keypad(True)

    # ---- state --------------------------------------------------------------

    @property
    def current(self) -> Game | None:
        return self.games[self.selected] if self.games else None

    def save(self) -> None:
        try:
            save_config(self.path, self.config)
        except HvrunnerError as error:
            self.status = str(error)

    def _keep_cursor_on(self, key: str) -> None:
        self.selected = next((index for index, game in enumerate(self.games) if game.key == key), 0)
        self.selected = min(self.selected, max(0, len(self.games) - 1))

    def rescan(self) -> None:
        previous = self.games[self.selected].key if self.games else ""
        self.games = library(self.config)
        self._keep_cursor_on(previous)

    def resort(self) -> None:
        """Re-sort what is already in memory after a favourite changed.

        Not a rescan. The scan walks every library folder and stats what it
        finds, which for one boolean is a tenth of a second of disk for nothing.
        """
        favourites = {str(item) for item in self.config["favorites"]}
        previous = self.games[self.selected].key if self.games else ""
        self.games = sort_games([replace(game, favorite=game.key in favourites) for game in self.games])
        self._keep_cursor_on(previous)

    def move(self, step: int) -> None:
        if self.games:
            self.selected = (self.selected + step) % len(self.games)

    def prompt(self, label: str, initial: str = "") -> str | None:
        value = prompt_module.ask(self.screen, self.theme, label, initial)
        if value is None and self.screen.getmaxyx()[1] < prompt_module.MINIMUM_WIDTH:
            self.status = "Terminal is too small for that"
        return str(value) if isinstance(value, str) else None

    def prompt_path(self, label: str, want: Want, initial: str = "") -> str | None:
        return ask_for_path(self, label, want, initial)

    def library_roots(self) -> list[Path]:
        return [Path(expand(str(root))) for root in self.config["library_roots"]]

    # ---- actions ------------------------------------------------------------

    def run_game(self, *, as_spacewar: bool = False) -> None:
        game = self.current
        if not game:
            return
        if as_spacewar:
            # An override, not the default: a game with no declared id already
            # runs as Spacewar. This is for the entry that declares a real
            # application the user does not own, where running as that id fails
            # and running as Spacewar works. A one off, because the replace
            # never reaches the config.
            game = replace(game, steam_appid=SPACEWAR_APPID)
        try:
            result = launch(game, self.config)
        except HvrunnerError as error:
            self.status = str(error)
            return
        self.active_log = result.log_path
        self.watching = Watch(game.name, result.pid, time.monotonic())
        self.status = f"Started {game.name}, pid {result.pid}. Press l for output."

    def check_launch(self) -> None:
        """Correct the started message once the process is gone.

        Without this a game that died on startup kept reporting itself as
        running for as long as the interface stayed open, which is how a failed
        launch went unnoticed in the first place.
        """
        watch = self.watching
        if watch is None or alive(watch.pid):
            return
        self.watching = None
        if time.monotonic() - watch.started < LAUNCH_SETTLE_SECONDS:
            self.status = f"{watch.name} exited on startup. Press l for output."
        else:
            self.status = f"{watch.name} has exited."

    def toggle_favourite(self) -> None:
        game = self.current
        if not game:
            return
        favourites = {str(item) for item in self.config["favorites"]}
        if game.key in favourites:
            favourites.remove(game.key)
            self.status = f"{game.name} is no longer a favourite"
        else:
            favourites.add(game.key)
            self.status = f"{game.name} is a favourite"
        self.config["favorites"] = sorted(favourites)
        self.save()
        self.resort()

    def add_executable(self) -> None:
        entered = self.prompt_path("Path to a game executable", Want.EXECUTABLE)
        if not entered:
            return
        path = Path(expand(entered))
        if not launchable(path):
            self.status = f"Nothing runnable at {path}"
            return
        # The library subdirectory, not the binary's own folder, so a game added
        # by hand and the same game found by the scan agree on where its prefix
        # lives rather than ending up with one each.
        folder = game_folder(path, self.library_roots())
        default = display_name(folder)
        name = self.prompt("Name it", default) or default
        entries.add(self.config, entries.declare(name, path, folder))
        self.save()
        self.rescan()
        self.status = f"Added {name}"

    def edit_entry(self) -> None:
        game = self.current
        if not game:
            return
        EntryScreen(self, game).run()

    def _install_root(self) -> Path | None:
        roots = self.library_roots()
        if not roots:
            self.status = "No library folder configured. Add one in settings."
            return None
        if len(roots) == 1:
            return roots[0]
        entered = self.prompt_path("Install into which library folder", Want.DIRECTORY, str(roots[0]))
        return Path(expand(entered)) if entered else None

    def install_game(self) -> None:
        entered = self.prompt_path("Path to a Windows installer", Want.EXECUTABLE)
        if not entered:
            return
        source = Path(expand(entered))
        # A Windows program specifically, not merely something runnable: this
        # one is handed to Proton, and a native binary given to Wine fails
        # without saying why.
        if not source.is_file() or not windows_program(source):
            self.status = f"Not a Windows installer: {source}"
            return
        name = self.prompt("Name it", source.stem) or source.stem
        root = self._install_root()
        if root is None:
            return
        try:
            target = installer.prepare_target(root, name)
            run = installer.start(source, target, self.config)
        except HvrunnerError as error:
            self.status = str(error)
            return
        # The log feed is the wait: it already polls, follows and leaves on esc.
        self.active_log = run.log_path
        self.status = f"Installing {name}. Close the installer, then press esc."
        self.open_logs()
        if installer.running(run):
            self.status = f"{name} is still installing. Press l for output."
            return
        self._register_installed(run, name)

    def _register_installed(self, run: installer.InstallRun, name: str) -> None:
        candidates = installer.discover(run.prefix, name)
        if not candidates:
            self.status = f"{name} installed, but no executable was found. Add it with a."
            return
        options = [(path.name, str(path)) for path in candidates]
        chosen = PickerScreen(self, "INSTALLED", name, options).choose()
        if chosen is None:
            self.status = f"{name} installed. Nothing was added to the library."
            return
        entries.add(self.config, entries.declare(name, candidates[chosen], run.target))
        self.save()
        self.rescan()
        self.status = f"Added {name}"

    # ---- navigation ---------------------------------------------------------

    def open_logs(self) -> None:
        screen = LogScreen(self)
        if not screen.available:
            self.status = "No output yet. Run a game first."
            return
        screen.run()

    def open_settings(self) -> None:
        SettingsScreen(self).run()

    def open_help(self) -> None:
        HelpScreen(self).run()

    def run(self) -> None:
        LibraryScreen(self).run()


def run_tui(config: dict[str, Any], path: Path) -> None:
    curses.wrapper(lambda screen: App(screen, config, path).run())
