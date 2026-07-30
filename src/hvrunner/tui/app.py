"""Library browser, launch preview, settings and log feed.

Layout is two panes: the library on the left, and on the right a preview of
exactly what will run. The preview is the point of the screen. Choosing a game
here means choosing a Proton build, a prefix, a MangoHud configuration and a set
of DXVK overrides, and none of that is visible from a filename.
"""

from __future__ import annotations

import contextlib
import curses
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import expand, save_config
from ..constants import APP_NAME
from ..launcher import WINDOWS_SIDE_ENV, launch, plan
from ..library import display_name, library
from ..logs import LogReader, classify, recent_logs
from ..models import Game, HvrunnerError
from .theme import Theme
from .widgets import Painter, Rect, draw_text, fit, letterspace, shorten_path

LIBRARY_KEYS = "enter run   l logs   s settings   f favourite   a add   r rescan   ? keys   q quit"
LOG_KEYS = "j k scroll   pgup pgdn page   g G ends   f follow   n p switch log   esc back"
SETTINGS_KEYS = "j k move   enter change   esc back"

# Below this the two pane layout stops being readable, so the preview is dropped.
TWO_PANE_MINIMUM = 74

LOG_ROLES = {
    "command": ("linux", {"bold": True}),
    "noise": ("rule", {}),
    "error": ("error", {}),
    "warning": ("warn", {}),
    "plain": ("text", {}),
}

HELP_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "library",
        [
            ("enter", "run the selected game"),
            ("j k", "move the cursor"),
            ("f", "favourite, which sorts it to the top"),
            ("a", "add an executable by path"),
            ("r", "rescan library folders"),
            ("l", "open the log feed"),
            ("s", "settings"),
            ("q", "quit"),
        ],
    ),
    (
        "log feed",
        [
            ("j k", "scroll a line"),
            ("pgup pgdn", "scroll a screen"),
            ("g G", "jump to the start or the end"),
            ("f", "follow new output"),
            ("n p", "switch to a newer or older log"),
        ],
    ),
    (
        "colour",
        [
            ("cyan", "the Linux side: Proton, umu, prefix"),
            ("purple", "the Windows side: the executable, DXVK, NVAPI"),
            ("grey", "log output already known to be harmless"),
        ],
    ),
]


@dataclass
class Setting:
    label: str
    detail: str
    value: Callable[[], str]
    activate: Callable[[], None]
    role: Callable[[], str] = lambda: "text"


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

    # ---- library ------------------------------------------------------------

    def draw_library(self) -> None:
        self.screen.erase()
        favourites = sum(1 for game in self.games if game.favorite)
        title = letterspace(APP_NAME.upper())
        meta = "1 title" if len(self.games) == 1 else f"{len(self.games)} titles"
        if favourites:
            meta += f" {self.paint.glyph('dot')} {favourites} favourite"
        inner = self.paint.frame(title, meta, LIBRARY_KEYS)
        # Below this there is no room for even one list row after the padding.
        if inner.height < 4:
            self.screen.refresh()
            return

        two_pane = inner.width >= TWO_PANE_MINIMUM
        list_width = min(38, max(24, inner.width // 3)) if two_pane else inner.width - 2
        list_left = inner.left + 1
        rows_top = inner.top + 1
        rows_available = inner.height - 3

        if not self.games:
            self.paint.text(rows_top, list_left, "No games yet.", inner.width - 2, "text", bold=True)
            self.paint.text(rows_top + 2, list_left, "s  add a library folder", inner.width - 2, "label")
            self.paint.text(rows_top + 3, list_left, "a  add a single executable", inner.width - 2, "label")
        else:
            start = max(0, min(self.selected - rows_available // 2, len(self.games) - rows_available))
            for offset, game in enumerate(self.games[start : start + rows_available]):
                index = start + offset
                selected = index == self.selected
                marker = self.paint.glyph("star") if game.favorite else " "
                label = f"{marker} {game.name}"
                role = "linux" if selected else "text"
                self.paint.row(rows_top + offset, list_left, list_width, label, role, selected)

        if two_pane:
            divider_x = list_left + list_width
            self.paint.divider(divider_x, inner.top, inner.height - 1)
            preview = Rect(
                top=rows_top,
                left=divider_x + 2,
                height=inner.height - 2,
                width=inner.right - divider_x - 2,
            )
            self.draw_preview(preview)

        if self.status:
            self.paint.text(inner.bottom, inner.left + 1, fit(self.status, inner.width - 2), inner.width - 2, "warn")
        self.screen.refresh()

    def draw_preview(self, area: Rect) -> None:
        game = self.current
        if not game or area.width < 12:
            return
        row = area.top
        executable = Path(game.executable)

        self.paint.text(row, area.left, fit(executable.name, area.width), area.width, "windows", bold=True)
        row += 1

        try:
            prepared = plan(game, self.config)
        except HvrunnerError as error:
            self.paint.text(row + 1, area.left, fit(str(error), area.width), area.width, "error")
            return

        state = "prefix ready" if prepared.prefix_ready else "first run, expect a long start"
        self.paint.text(row, area.left, fit(state, area.width), area.width, "ok" if prepared.prefix_ready else "warn")
        row += 2

        if row < area.bottom:
            self.paint.section(row, area.left, area.width, "command")
            row += 1
            # Each wrapper indents, so the layering is visible: gamemode wraps
            # MangoHud wraps umu wraps the Windows binary.
            for depth, part in enumerate(prepared.command):
                if row > area.bottom - 1:
                    break
                indent = min(depth * 2, max(0, area.width - 8))
                name = Path(part).name if part.startswith("/") else part
                role = "windows" if name.casefold().endswith(".exe") else "linux"
                self.paint.text(row, area.left + indent, fit(name, area.width - indent), area.width - indent, role)
                row += 1
            row += 1

        if row < area.bottom:
            self.paint.section(row, area.left, area.width, "environment")
            row += 1
            entries = prepared.notable_environment()
            # One shared label column, otherwise the values sit ragged.
            column = min(max((len(name) for name, _ in entries), default=1) + 1, max(1, area.width // 2))
            for name, value in entries:
                if row > area.bottom:
                    break
                shown = Path(value).name if value.startswith("/") else value
                role = "windows" if name in WINDOWS_SIDE_ENV else "linux"
                self.paint.field(row, area.left, area.width, name, shown, role, name_width=column)
                row += 1

        if game.launch_args and row < area.bottom:
            row += 1
            self.paint.section(row, area.left, area.width, "arguments")
            self.paint.text(row + 1, area.left, fit(" ".join(game.launch_args), area.width), area.width, "text")

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

    # ---- prompt -------------------------------------------------------------

    def prompt(self, label: str, initial: str = "") -> str | None:
        height, width = self.paint.size
        box_width = min(max(40, len(label) + 8), max(20, width - 4))
        if width < 24 or height < 7:
            self.status = "Terminal is too small for that"
            return None
        top = max(0, height // 2 - 2)
        left = max(0, (width - box_width) // 2)
        window = curses.newwin(4, box_width, top, left)
        window.bkgd(" ", self.theme.attr("text"))
        window.erase()
        with contextlib.suppress(curses.error):
            window.border()

        draw_text(window, 1, 2, fit(label, box_width - 4), box_width - 4, self.theme.attr("label"))
        field_width = box_width - 4
        draw_text(window, 2, 2, initial[:field_width], field_width, self.theme.attr("text"))
        window.refresh()
        curses.echo()
        curses.curs_set(1)
        try:
            raw = window.getstr(2, 2, field_width)
            value = raw.decode(errors="replace").strip() if raw else ""
        except curses.error:
            value = ""
        finally:
            curses.noecho()
            curses.curs_set(0)
            del window
            self.screen.touchwin()
        return value or None

    # ---- help ---------------------------------------------------------------

    def show_help(self) -> None:
        while True:
            self.screen.erase()
            inner = self.paint.frame(letterspace("KEYS"), "", "any key returns")
            row = inner.top + 1
            for heading, entries in HELP_SECTIONS:
                if row >= inner.bottom:
                    break
                self.paint.section(row, inner.left + 1, inner.width - 2, heading)
                row += 1
                for combination, description in entries:
                    if row >= inner.bottom:
                        break
                    self.paint.text(row, inner.left + 2, combination.ljust(11), 11, "linux")
                    self.paint.text(row, inner.left + 14, fit(description, inner.width - 15), inner.width - 15, "text")
                    row += 1
                row += 1
            self.screen.refresh()
            if self.screen.getch() not in (-1, curses.KEY_RESIZE):
                return

    # ---- settings -----------------------------------------------------------

    def build_settings(self) -> list[Setting]:
        def toggle(key: str, default: bool) -> Callable[[], None]:
            def action() -> None:
                self.config[key] = not self.config.get(key, default)
                self.save()

            return action

        def on_off(key: str, default: bool, labels: tuple[str, str]) -> Callable[[], str]:
            return lambda: labels[0] if self.config.get(key, default) else labels[1]

        def edit_path(key: str, label: str) -> Callable[[], None]:
            def action() -> None:
                entered = self.prompt(label, str(self.config[key]))
                if entered:
                    self.config[key] = expand(entered)
                    self.save()

            return action

        def add_root() -> None:
            entered = self.prompt("Folder whose subdirectories hold games")
            if not entered:
                return
            resolved = expand(entered)
            if not Path(resolved).is_dir():
                self.status = f"No folder at {resolved}"
                return
            self.config["library_roots"] = list(dict.fromkeys([*self.config["library_roots"], resolved]))
            self.save()
            self.rescan()

        def remove_root() -> None:
            entered = self.prompt("Folder to stop scanning")
            if not entered:
                return
            resolved = expand(entered)
            remaining = [root for root in self.config["library_roots"] if str(root) != resolved]
            if len(remaining) == len(self.config["library_roots"]):
                self.status = f"{resolved} was not in the list"
                return
            self.config["library_roots"] = remaining
            self.save()
            self.rescan()

        return [
            Setting(
                "Proton build",
                "The Proton runtime every game is launched with.",
                lambda: str(self.config["proton_path"]),
                edit_path("proton_path", "Path to a Proton build"),
                lambda: "linux",
            ),
            Setting(
                "umu runner",
                "umu supplies the Steam Linux Runtime container Proton needs.",
                lambda: str(self.config["umu_path"]),
                edit_path("umu_path", "Path to umu-run"),
                lambda: "linux",
            ),
            Setting(
                "Library folders",
                "Each subdirectory of these folders is scanned for an executable.",
                lambda: f"{len(self.config['library_roots'])} folders",
                add_root,
            ),
            Setting(
                "Stop scanning a folder",
                "Remove a folder from the scan list.",
                lambda: ", ".join(str(root) for root in self.config["library_roots"]) or "none",
                remove_root,
            ),
            Setting(
                "Presentation",
                "Native Wayland skips XWayland. Frame pacing differs between them.",
                on_off("enable_wayland", False, ("native Wayland", "XWayland")),
                toggle("enable_wayland", False),
                lambda: "ok" if self.config.get("enable_wayland") else "text",
            ),
            Setting(
                "gamemode",
                "Applies gamemode's scheduling tweaks. Off silences its dlopen warnings.",
                on_off("use_gamemode", True, ("on", "off")),
                toggle("use_gamemode", True),
                lambda: "ok" if self.config.get("use_gamemode", True) else "text",
            ),
            Setting(
                "Spread across all CPUs",
                "Keeps game threads on every core, undoing masks a game sets itself.",
                on_off("enforce_all_cpus", True, ("on", "off")),
                toggle("enforce_all_cpus", True),
                lambda: "ok" if self.config.get("enforce_all_cpus", True) else "text",
            ),
        ]

    def settings(self) -> None:
        settings = self.build_settings()
        cursor = 0
        while True:
            self.screen.erase()
            inner = self.paint.frame(letterspace("SETTINGS"), str(self.path), SETTINGS_KEYS)
            if inner.height < 3:
                self.screen.refresh()
                if self.screen.getch() in (27, ord("q")):
                    return
                continue

            two_pane = inner.width >= TWO_PANE_MINIMUM
            list_width = min(34, max(22, inner.width // 3)) if two_pane else inner.width - 2
            list_left = inner.left + 1
            row_top = inner.top + 1

            for offset, setting in enumerate(settings):
                selected = offset == cursor
                self.paint.row(
                    row_top + offset,
                    list_left,
                    list_width,
                    setting.label,
                    "linux" if selected else "text",
                    selected,
                )

            if two_pane:
                divider_x = list_left + list_width
                self.paint.divider(divider_x, inner.top, inner.height - 1)
                left = divider_x + 2
                width = inner.right - divider_x - 2
                chosen = settings[cursor]
                self.paint.text(row_top, left, fit(chosen.label, width), width, "text", bold=True)
                self.paint.text(
                    row_top + 2,
                    left,
                    shorten_path(chosen.value(), width, self.paint.glyph("ellipsis")),
                    width,
                    chosen.role(),
                )
                self.paint.section(row_top + 4, left, width, "about")
                for index, line in enumerate(self._wrap(chosen.detail, width)):
                    self.paint.text(row_top + 5 + index, left, line, width, "label")

            if self.status:
                self.paint.text(inner.bottom, inner.left + 1, fit(self.status, inner.width - 2), inner.width - 2, "warn")
            self.screen.refresh()

            key = self.screen.getch()
            if key in (27, ord("q")):
                return
            if key in (curses.KEY_DOWN, ord("j")):
                cursor = (cursor + 1) % len(settings)
            elif key in (curses.KEY_UP, ord("k")):
                cursor = (cursor - 1) % len(settings)
            elif key in (10, 13, curses.KEY_ENTER, ord(" ")):
                settings[cursor].activate()

    @staticmethod
    def _wrap(text: str, width: int) -> list[str]:
        if width <= 0:
            return []
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) > width and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    # ---- log feed -----------------------------------------------------------

    def open_logs(self) -> None:
        available = recent_logs()
        if self.active_log and self.active_log not in available:
            available.insert(0, self.active_log)
        if not available:
            self.status = "No output yet. Run a game first."
            return
        index = available.index(self.active_log) if self.active_log in available else 0
        reader = LogReader(available[index])
        offset = 0
        follow = True
        self.screen.timeout(400)
        try:
            while True:
                reader.poll()
                height, _ = self.paint.size
                rows = max(1, height - 3)
                if follow:
                    offset = max(0, len(reader.lines) - rows)
                self._draw_log(available[index], reader, offset, follow, len(available), index)

                key = self.screen.getch()
                if key in (-1, curses.KEY_RESIZE):
                    continue
                if key in (27, ord("q")):
                    return
                if key in (curses.KEY_DOWN, ord("j")):
                    offset, follow = min(offset + 1, max(0, len(reader.lines) - 1)), False
                elif key in (curses.KEY_UP, ord("k")):
                    offset, follow = max(0, offset - 1), False
                elif key == curses.KEY_NPAGE:
                    offset, follow = min(offset + rows, max(0, len(reader.lines) - 1)), False
                elif key == curses.KEY_PPAGE:
                    offset, follow = max(0, offset - rows), False
                elif key == ord("g"):
                    offset, follow = 0, False
                elif key == ord("G"):
                    follow = True
                elif key == ord("f"):
                    follow = not follow
                elif key in (ord("n"), ord("p")):
                    step = -1 if key == ord("n") else 1
                    moved = min(max(index + step, 0), len(available) - 1)
                    if moved != index:
                        index = moved
                        reader = LogReader(available[index])
                        offset, follow = 0, True
        finally:
            self.screen.timeout(-1)

    def _draw_log(self, path: Path, reader: LogReader, offset: int, follow: bool, total: int, index: int) -> None:
        self.screen.erase()
        dot = self.paint.glyph("dot")
        position = f"{index + 1}/{total}" if total > 1 else ""
        meta = f"{len(reader.lines)} lines {dot} {'following' if follow else 'paused'}"
        if position:
            meta = f"{position} {dot} {meta}"
        inner = self.paint.frame(path.name, meta, LOG_KEYS)
        if inner.height < 2:
            self.screen.refresh()
            return

        rows = inner.height
        gutter = len(str(max(1, len(reader.lines)))) + 1
        text_left = inner.left + gutter + 1
        text_width = inner.right - text_left
        visible = reader.lines[offset : offset + rows]
        if not visible:
            self.paint.text(inner.top, text_left, "Waiting for output.", max(0, text_width), "label")
        for line_offset, line in enumerate(visible):
            row = inner.top + line_offset
            number = str(offset + line_offset + 1).rjust(gutter)
            self.paint.text(row, inner.left, number, gutter, "rule")
            role, attributes = LOG_ROLES[classify(line)]
            self.paint.text(row, text_left, fit(line, max(0, text_width)), max(0, text_width), role, **attributes)
        self.screen.refresh()

    # ---- main loop ----------------------------------------------------------

    def run(self) -> None:
        while True:
            self.draw_library()
            key = self.screen.getch()
            if key in (ord("q"), 27):
                return
            if key == curses.KEY_RESIZE:
                continue
            if key in (curses.KEY_DOWN, ord("j")):
                self.move(1)
            elif key in (curses.KEY_UP, ord("k")):
                self.move(-1)
            elif key in (10, 13, curses.KEY_ENTER):
                self.run_game()
            elif key == ord("f"):
                self.toggle_favourite()
            elif key == ord("r"):
                self.rescan()
                self.status = f"{len(self.games)} titles"
            elif key == ord("a"):
                self.add_executable()
            elif key == ord("l"):
                self.open_logs()
            elif key == ord("s"):
                self.settings()
            elif key == ord("?"):
                self.show_help()


def run_tui(config: dict[str, Any], path: Path) -> None:
    curses.wrapper(lambda screen: App(screen, config, path).run())
