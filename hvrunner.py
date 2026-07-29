#!/usr/bin/env python3
"""hvrunner terminal game library and Proton launcher.

hvrunner is self-contained: custom Windows games are launched
directly with the configured Proton build.  It never calls per-game run.sh
scripts or depends on game-folder launcher wrappers.
"""

from __future__ import annotations

import argparse
import curses
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

APP_NAME = "hvrunner"
DEFAULT_COMPAT_ROOT = Path.home() / ".local/share/Steam"
DEFAULT_PROTON = DEFAULT_COMPAT_ROOT / "compatibilitytools.d/Proton-GE11-1-LinUwUx/proton"
DEFAULT_CUSTOM_ROOT = Path("/mnt/data/games")


@dataclass(frozen=True)
class Game:
    name: str
    source: str
    install_dir: str
    executable: str = ""
    appid: str = ""
    launch_args: tuple[str, ...] = ()
    favorite: bool = False

    @property
    def key(self) -> str:
        return f"{self.source}:{self.appid or self.executable or self.install_dir}"


def config_path() -> Path:
    configured = os.environ.get("HVRUNNER_CONFIG")
    if configured:
        return Path(configured).expanduser()
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "hvrunner" / "config.json"


def default_config() -> dict[str, Any]:
    return {
        "library_roots": [str(DEFAULT_CUSTOM_ROOT)],
        "proton_path": str(DEFAULT_PROTON),
        "compat_client_path": str(DEFAULT_COMPAT_ROOT),
        "custom_prefix_name": ".hvrunner-proton",
        "enforce_all_cpus": True,
        "favorites": [],
        "custom_games": [],
    }


def load_config(path: Path) -> dict[str, Any]:
    config = default_config()
    if not path.exists():
        return config
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot read {path}: {error}") from error
    if not isinstance(data, dict):
        raise RuntimeError(f"cannot read {path}: top level must be an object")
    for key, value in data.items():
        if key in config:
            config[key] = value
    return config


def save_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def display_name(folder: Path) -> str:
    return re.sub(r"[._-]+", " ", folder.name).strip().title() or folder.name


def select_executable(folder: Path) -> Path | None:
    executables = sorted(
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() == ".exe"
    )
    if not executables:
        return None
    non_installers = [path for path in executables if not re.search(r"(unins|setup|install|crash)", path.name, re.I)]
    return (non_installers or executables)[0]


def custom_games(config: dict[str, Any], favorites: set[str]) -> list[Game]:
    games: list[Game] = []
    seen: set[str] = set()
    for root_text in config["library_roots"]:
        root = Path(root_text).expanduser()
        if not root.is_dir():
            continue
        for folder in sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")):
            executable = select_executable(folder)
            if executable is None:
                continue
            key = f"custom:{executable}"
            seen.add(str(executable))
            games.append(Game(display_name(folder), "Custom", str(folder), str(executable), favorite=key in favorites))

    for entry in config["custom_games"]:
        if not isinstance(entry, dict):
            continue
        executable = Path(str(entry.get("executable", ""))).expanduser()
        if not executable.is_file() or str(executable) in seen:
            continue
        name = str(entry.get("name") or display_name(executable.parent))
        arguments = tuple(str(arg) for arg in entry.get("launch_args", []) if isinstance(arg, str))
        key = f"custom:{executable}"
        games.append(Game(name, "Custom", str(executable.parent), str(executable), launch_args=arguments, favorite=key in favorites))
    return games


def library(config: dict[str, Any]) -> list[Game]:
    favorites = set(str(item) for item in config["favorites"])
    games = custom_games(config, favorites)
    return sorted(games, key=lambda game: (not game.favorite, game.name.casefold(), game.source))


def custom_launch_command(game: Game, config: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    proton = Path(str(config["proton_path"])).expanduser()
    mangohud = shutil.which("mangohud")
    executable = Path(game.executable)
    if not proton.is_file():
        raise RuntimeError(f"Proton is unavailable: {proton}")
    if not mangohud:
        raise RuntimeError("MangoHud is unavailable")
    if not executable.is_file():
        raise RuntimeError(f"game executable is unavailable: {executable}")
    compat_client_path = Path(str(config["compat_client_path"])).expanduser()
    if not compat_client_path.is_dir():
        raise RuntimeError(f"Proton compatibility client path is unavailable: {compat_client_path}")
    prefix = Path(game.install_dir) / str(config["custom_prefix_name"])
    prefix.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update({
        "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(compat_client_path),
        "STEAM_COMPAT_DATA_PATH": str(prefix),
        "WINEPREFIX": str(prefix / "pfx"),
        "WINEDEBUG": "-all",
        "PROTON_USE_XALIA": "0",
        "DISABLE_GAMESCOPE_WSI": "1",
        "MANGOHUD": "1",
        "MANGOHUD_CONFIG": "full,toggle_hud=Shift_R+F12",
    })
    environment.pop("PROTON_ENABLE_WAYLAND", None)
    return [mangohud, str(proton), "run", str(executable), *game.launch_args], environment


def matching_game_pids(executable_name: str, install_dir: str) -> list[int]:
    expected_comm = executable_name[:15]
    expected_cwd = Path(install_dir).resolve()
    matches: list[int] = []
    for process_dir in Path("/proc").iterdir():
        if not process_dir.name.isdigit():
            continue
        try:
            comm = (process_dir / "comm").read_text().strip()
            cwd = (process_dir / "cwd").resolve()
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if comm == expected_comm and cwd == expected_cwd:
            matches.append(int(process_dir.name))
    return matches


def set_full_affinity(pid: int, cpus: set[int]) -> None:
    task_dir = Path(f"/proc/{pid}/task")
    try:
        thread_ids = [int(path.name) for path in task_dir.iterdir() if path.name.isdigit()]
    except (FileNotFoundError, PermissionError, OSError):
        return
    for thread_id in thread_ids:
        try:
            if os.sched_getaffinity(thread_id) != cpus:
                os.sched_setaffinity(thread_id, cpus)
        except (ProcessLookupError, PermissionError, OSError):
            continue


def affinity_watch(executable_name: str, install_dir: str) -> None:
    cpus = set(os.sched_getaffinity(0))
    startup_deadline = time.monotonic() + 120
    missing_since: float | None = None
    game_seen = False
    while True:
        matches = matching_game_pids(executable_name, install_dir)
        now = time.monotonic()
        if matches:
            game_seen = True
            missing_since = None
            for pid in matches:
                set_full_affinity(pid, cpus)
        elif not game_seen:
            if now >= startup_deadline:
                return
        else:
            if missing_since is None:
                missing_since = now
            elif now - missing_since >= 3:
                return
        time.sleep(0.25)


def launch(game: Game, config: dict[str, Any]) -> None:
    command, environment = custom_launch_command(game, config)
    subprocess.Popen(command, cwd=game.install_dir, env=environment, start_new_session=True)
    if config.get("enforce_all_cpus", True):
        subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--affinity-watch",
                Path(game.executable).name,
                game.install_dir,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


class Tui:
    def __init__(self, screen: curses.window, config: dict[str, Any], path: Path):
        self.screen, self.config, self.path = screen, config, path
        self.games = library(config)
        self.selected = 0
        self.message = "Ready"
        curses.curs_set(0)
        self.screen.keypad(True)

    def refresh(self) -> None:
        old_key = self.games[self.selected].key if self.games else ""
        self.games = library(self.config)
        self.selected = next((i for i, game in enumerate(self.games) if game.key == old_key), 0)
        self.selected = min(self.selected, max(0, len(self.games) - 1))

    def prompt(self, label: str, initial: str = "") -> str | None:
        height, width = self.screen.getmaxyx()
        field_width = max(20, width - len(label) - 5)
        window = curses.newwin(3, width - 2, max(0, height // 2 - 1), 1)
        window.box()
        window.addstr(1, 2, label)
        curses.echo()
        curses.curs_set(1)
        try:
            window.addstr(1, len(label) + 3, initial[:field_width])
            window.move(1, len(label) + 3 + len(initial[:field_width]))
            value = window.getstr(1, len(label) + 3, field_width).decode(errors="replace").strip()
        except curses.error:
            value = ""
        finally:
            curses.noecho()
            curses.curs_set(0)
        return value or None

    def draw(self) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        title = f" {APP_NAME}  •  {len(self.games)} games "
        self.screen.attron(curses.A_REVERSE)
        self.screen.addnstr(0, 0, title.ljust(width), width)
        self.screen.attroff(curses.A_REVERSE)
        if not self.games:
            self.screen.addnstr(3, 2, "No games found. Press s to add library folders or a to add an executable.", width - 4)
        else:
            rows = max(1, height - 5)
            start = max(0, min(self.selected - rows // 2, len(self.games) - rows))
            for row, game in enumerate(self.games[start:start + rows], start=1):
                index = start + row - 1
                marker = "★" if game.favorite else " "
                line = f"{marker} {game.name}  [{game.source}]"
                if index == self.selected:
                    self.screen.attron(curses.A_REVERSE)
                self.screen.addnstr(row, 1, line.ljust(width - 2), width - 2)
                if index == self.selected:
                    self.screen.attroff(curses.A_REVERSE)
            selected = self.games[self.selected]
            self.screen.addnstr(height - 3, 1, selected.executable, width - 2)
        self.screen.attron(curses.A_REVERSE)
        footer = "Enter launch  s settings  a add exe  f favorite  r rescan  q quit"
        footer_width = max(0, width - 1)
        self.screen.addnstr(height - 1, 0, footer.ljust(footer_width), footer_width)
        self.screen.attroff(curses.A_REVERSE)
        self.screen.addnstr(height - 2, 1, self.message, width - 2)
        self.screen.refresh()

    def toggle_favorite(self) -> None:
        if not self.games:
            return
        game = self.games[self.selected]
        favorites = set(str(item) for item in self.config["favorites"])
        if game.key in favorites:
            favorites.remove(game.key)
            self.message = f"Removed {game.name} from favorites"
        else:
            favorites.add(game.key)
            self.message = f"Added {game.name} to favorites"
        self.config["favorites"] = sorted(favorites)
        save_config(self.path, self.config)
        self.refresh()

    def add_executable(self) -> None:
        executable = self.prompt("Executable path:")
        if not executable:
            return
        path = Path(executable).expanduser()
        if not path.is_file() or path.suffix.lower() != ".exe":
            self.message = "That is not a readable .exe file"
            return
        name = self.prompt("Name:", display_name(path.parent)) or display_name(path.parent)
        self.config["custom_games"].append({"name": name, "executable": str(path)})
        save_config(self.path, self.config)
        self.message = f"Added {name}"
        self.refresh()

    def settings(self) -> None:
        while True:
            self.screen.erase()
            height, width = self.screen.getmaxyx()
            entries = [
                ("Proton", str(self.config["proton_path"])),
                ("Proton client path", str(self.config["compat_client_path"])),
                ("Add library", "Scan immediate subdirectories for .exe files"),
                ("Remove library", ", ".join(self.config["library_roots"]) or "None"),
                ("Back", "Return to library"),
            ]
            self.screen.addnstr(0, 0, " hvrunner settings ".ljust(width), width, curses.A_REVERSE)
            for index, (label, value) in enumerate(entries, start=2):
                self.screen.addnstr(index, 2, f"{index - 2 + 1}. {label}", width - 4)
                self.screen.addnstr(index, 24, value, width - 26, curses.A_DIM)
            footer_width = max(0, width - 1)
            self.screen.addnstr(height - 1, 0, "1-5 select  Esc back".ljust(footer_width), footer_width, curses.A_REVERSE)
            self.screen.refresh()
            key = self.screen.getch()
            if key in (27, ord("q"), ord("5")):
                return
            if key == ord("1"):
                value = self.prompt("Proton path:", str(self.config["proton_path"]))
                if value:
                    self.config["proton_path"] = str(Path(value).expanduser())
                    save_config(self.path, self.config)
            elif key == ord("2"):
                value = self.prompt("Proton client path:", str(self.config["compat_client_path"]))
                if value:
                    self.config["compat_client_path"] = str(Path(value).expanduser())
                    save_config(self.path, self.config)
            elif key == ord("3"):
                value = self.prompt("Custom library folder:")
                if value and Path(value).expanduser().is_dir():
                    roots = list(dict.fromkeys([*self.config["library_roots"], str(Path(value).expanduser())]))
                    self.config["library_roots"] = roots
                    save_config(self.path, self.config)
                elif value:
                    self.message = "Folder does not exist"
            elif key == ord("4"):
                value = self.prompt("Exact folder to remove:")
                if value:
                    value = str(Path(value).expanduser())
                    self.config["library_roots"] = [root for root in self.config["library_roots"] if root != value]
                    save_config(self.path, self.config)
            self.refresh()

    def run(self) -> None:
        while True:
            self.draw()
            key = self.screen.getch()
            if key in (ord("q"), 27):
                return
            if key in (curses.KEY_UP, ord("k")) and self.games:
                self.selected = (self.selected - 1) % len(self.games)
            elif key in (curses.KEY_DOWN, ord("j")) and self.games:
                self.selected = (self.selected + 1) % len(self.games)
            elif key in (10, 13, curses.KEY_ENTER) and self.games:
                game = self.games[self.selected]
                try:
                    launch(game, self.config)
                    self.message = f"Launching {game.name}"
                except RuntimeError as error:
                    self.message = str(error)
            elif key == ord("f"):
                self.toggle_favorite()
            elif key == ord("r"):
                self.refresh()
                self.message = "Library rescanned"
            elif key == ord("a"):
                self.add_executable()
            elif key == ord("s"):
                self.settings()


def main() -> int:
    parser = argparse.ArgumentParser(description="hvrunner terminal game launcher")
    parser.add_argument("--list", action="store_true", help="print discovered games without opening the TUI")
    parser.add_argument("--init-config", action="store_true", help="write default configuration if it is absent")
    parser.add_argument("--affinity-watch", nargs=2, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.affinity_watch:
        affinity_watch(args.affinity_watch[0], args.affinity_watch[1])
        return 0
    path = config_path()
    try:
        config = load_config(path)
        if args.init_config:
            if not path.exists():
                save_config(path, config)
                print(f"Created {path}")
            else:
                print(f"Configuration already exists: {path}")
            return 0
        games = library(config)
        if args.list:
            for game in games:
                target = game.appid if game.source == "Steam" else game.executable
                print(f"{game.source}\t{game.name}\t{target}")
            return 0
        curses.wrapper(lambda screen: Tui(screen, config, path).run())
    except RuntimeError as error:
        print(f"{APP_NAME}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
