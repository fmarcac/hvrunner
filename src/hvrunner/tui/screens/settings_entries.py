"""What the settings are, and what changing each one does.

Separate from the screen that presents them: this module knows the config, the
screen knows the layout.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ...core.browsing import Want
from ...core.config import expand

if TYPE_CHECKING:
    from ..app import App


@dataclass
class Setting:
    label: str
    detail: str
    value: Callable[[], str]
    activate: Callable[[], None]
    role: Callable[[], str]


def _toggle(app: App, key: str, default: bool) -> Callable[[], None]:
    def action() -> None:
        app.config[key] = not app.config.get(key, default)
        app.save()

    return action


def _state(app: App, key: str, default: bool, when_on: str, when_off: str) -> Callable[[], str]:
    return lambda: when_on if app.config.get(key, default) else when_off


def _role(app: App, key: str, default: bool) -> Callable[[], str]:
    return lambda: "ok" if app.config.get(key, default) else "text"


def _edit_path(app: App, key: str, label: str, want: Want) -> Callable[[], None]:
    def action() -> None:
        entered = app.prompt_path(label, want, str(app.config[key]))
        if entered:
            app.config[key] = expand(entered)
            app.save()

    return action


def _add_root(app: App) -> Callable[[], None]:
    def action() -> None:
        entered = app.prompt_path("Folder whose subdirectories hold games", Want.DIRECTORY)
        if not entered:
            return
        resolved = expand(entered)
        if not Path(resolved).is_dir():
            app.status = f"No folder at {resolved}"
            return
        app.config["library_roots"] = list(dict.fromkeys([*app.config["library_roots"], resolved]))
        app.save()
        app.rescan()
        app.status = f"Scanning {resolved}"

    return action


def _remove_root(app: App) -> Callable[[], None]:
    def action() -> None:
        entered = app.prompt("Folder to stop scanning")
        if not entered:
            return
        resolved = expand(entered)
        remaining = [root for root in app.config["library_roots"] if str(root) != resolved]
        if len(remaining) == len(app.config["library_roots"]):
            app.status = f"{resolved} was not in the list"
            return
        app.config["library_roots"] = remaining
        app.save()
        app.rescan()
        app.status = f"No longer scanning {resolved}"

    return action


def build(app: App) -> list[Setting]:
    config = app.config
    return [
        Setting(
            "Proton build",
            "The Proton runtime every game is launched with.",
            lambda: str(config["proton_path"]),
            _edit_path(app, "proton_path", "Path to a Proton build", Want.DIRECTORY),
            lambda: "linux",
        ),
        Setting(
            "umu runner",
            "umu supplies the Steam Linux Runtime container Proton needs.",
            lambda: str(config["umu_path"]),
            # A plain file, not a .exe: umu-run has no extension at all.
            _edit_path(app, "umu_path", "Path to umu-run", Want.FILE),
            lambda: "linux",
        ),
        Setting(
            "Library folders",
            "Each subdirectory of these folders is scanned for an executable.",
            lambda: f"{len(config['library_roots'])} folders",
            _add_root(app),
            lambda: "text",
        ),
        Setting(
            "Stop scanning a folder",
            "Remove a folder from the scan list.",
            lambda: ", ".join(str(root) for root in config["library_roots"]) or "none",
            _remove_root(app),
            lambda: "text",
        ),
        Setting(
            "Shader cache",
            "Keeps compiled pipelines between runs. Without it every launch "
            "recompiles shaders as they appear, which shows up as frametime spikes.",
            _state(app, "shader_cache", True, "on", "off"),
            _toggle(app, "shader_cache", True),
            _role(app, "shader_cache", True),
        ),
        Setting(
            "Native scale while playing",
            "Drops the output to scale 1 for the game and restores it afterwards. "
            "A scaled output makes the compositor rescale every frame, which "
            "prevents direct scanout and caps the frame rate.",
            _state(app, "native_scale", False, "on", "off"),
            _toggle(app, "native_scale", False),
            _role(app, "native_scale", False),
        ),
        Setting(
            "Presentation",
            "Native Wayland skips XWayland. Frame pacing differs between the two.",
            _state(app, "enable_wayland", False, "native Wayland", "XWayland"),
            _toggle(app, "enable_wayland", False),
            _role(app, "enable_wayland", False),
        ),
        Setting(
            "MangoHud overlay",
            "Wraps the command in mangohud and sets MANGOHUD=1. Off removes both. "
            "A machine without MangoHud installed launches without it either way.",
            _state(app, "use_mangohud", True, "on", "off"),
            _toggle(app, "use_mangohud", True),
            _role(app, "use_mangohud", True),
        ),
        Setting(
            "gamemode",
            "Applies gamemode's scheduling changes. Off silences its dlopen warnings.",
            _state(app, "use_gamemode", True, "on", "off"),
            _toggle(app, "use_gamemode", True),
            _role(app, "use_gamemode", True),
        ),
        Setting(
            "Spread across all CPUs",
            "Keeps game threads on every core, undoing masks a game sets itself.",
            _state(app, "enforce_all_cpus", True, "on", "off"),
            _toggle(app, "enforce_all_cpus", True),
            _role(app, "enforce_all_cpus", True),
        ),
    ]
