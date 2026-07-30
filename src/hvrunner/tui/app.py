"""Application shell.

Holds the state the screens read and the actions they invoke. Drawing and key
handling live in the individual screens.
"""

from __future__ import annotations

import curses
from pathlib import Path
from typing import Any

from ..config import expand, save_config
from ..launcher import launch
from ..library import display_name, library
from ..models import Game, HvrunnerError
from . import prompt as prompt_module
from .screens import HelpScreen, LibraryScreen, LogScreen, SettingsScreen
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
