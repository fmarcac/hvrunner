"""Application shell.

Holds the state the screens read and the actions they invoke. Drawing and key
handling live in the individual screens.
"""

from __future__ import annotations

import curses
from pathlib import Path
from typing import Any

from .. import entries, installer
from ..config import expand, save_config
from ..launcher import launch
from ..library import display_name, library
from ..models import Game, HvrunnerError
from . import prompt as prompt_module
from .screens import EntryScreen, HelpScreen, LibraryScreen, LogScreen, PickerScreen, SettingsScreen
from .theme import Theme
from .widgets import Painter


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
        self.status = ""
        self.active_log: Path | None = None
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

    def rescan(self) -> None:
        previous = self.games[self.selected].key if self.games else ""
        self.games = library(self.config)
        self.selected = next((i for i, game in enumerate(self.games) if game.key == previous), 0)
        self.selected = min(self.selected, max(0, len(self.games) - 1))

    def move(self, step: int) -> None:
        if self.games:
            self.selected = (self.selected + step) % len(self.games)

    def prompt(self, label: str, initial: str = "") -> str | None:
        value = prompt_module.ask(self.screen, self.theme, label, initial)
        if value is None and self.screen.getmaxyx()[1] < prompt_module.MINIMUM_WIDTH:
            self.status = "Terminal is too small for that"
        return value

    # ---- actions ------------------------------------------------------------

    def run_game(self) -> None:
        game = self.current
        if not game:
            return
        try:
            result = launch(game, self.config)
        except HvrunnerError as error:
            self.status = str(error)
            return
        self.active_log = result.log_path
        self.status = f"Running {game.name}, pid {result.pid}. Press l for output."

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
        self.rescan()

    def add_executable(self) -> None:
        entered = self.prompt("Path to a Windows executable")
        if not entered:
            return
        path = Path(expand(entered))
        if not path.is_file() or path.suffix.lower() != ".exe":
            self.status = f"No readable .exe at {path}"
            return
        default = display_name(path.parent)
        name = self.prompt("Name it", default) or default
        self.config["custom_games"].append({"name": name, "executable": str(path)})
        self.save()
        self.rescan()
        self.status = f"Added {name}"

    def edit_entry(self) -> None:
        game = self.current
        if not game:
            return
        EntryScreen(self, game).run()

    def _install_root(self) -> Path | None:
        roots = [Path(expand(str(root))) for root in self.config["library_roots"]]
        if not roots:
            self.status = "No library folder configured. Add one in settings."
            return None
        if len(roots) == 1:
            return roots[0]
        entered = self.prompt("Install into which library folder", str(roots[0]))
        return Path(expand(entered)) if entered else None

    def install_game(self) -> None:
        entered = self.prompt("Path to a Windows installer")
        if not entered:
            return
        source = Path(expand(entered))
        if not source.is_file() or source.suffix.lower() != ".exe":
            self.status = f"No readable .exe at {source}"
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
        entries.add(
            self.config,
            {
                "name": name,
                "executable": str(candidates[chosen]),
                "install_dir": str(run.target),
                "launch_args": [],
            },
        )
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
