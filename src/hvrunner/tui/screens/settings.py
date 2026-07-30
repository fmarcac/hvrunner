"""Settings.

Each entry explains what it changes, because these choices alter frame pacing
and process scheduling in ways a bare label cannot convey.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ...config import expand
from .. import keys, layout
from ..widgets import Rect, fit, letterspace, shorten_path, wrap
from .base import Screen

KEYS = "j k move   enter change   esc back"


@dataclass
class Setting:
    label: str
    detail: str
    value: Callable[[], str]
    activate: Callable[[], None]
    role: Callable[[], str]


class SettingsScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.cursor = 0
        self.settings = self._build()

    # ---- entries ------------------------------------------------------------

    def _toggle(self, key: str, default: bool) -> Callable[[], None]:
        def action() -> None:
            self.app.config[key] = not self.app.config.get(key, default)
            self.app.save()

        return action

    def _state(self, key: str, default: bool, when_on: str, when_off: str) -> Callable[[], str]:
        return lambda: when_on if self.app.config.get(key, default) else when_off

    def _role(self, key: str, default: bool) -> Callable[[], str]:
        return lambda: "ok" if self.app.config.get(key, default) else "text"

    def _edit_path(self, key: str, label: str) -> Callable[[], None]:
        def action() -> None:
            entered = self.app.prompt(label, str(self.app.config[key]))
            if entered:
                self.app.config[key] = expand(entered)
                self.app.save()

        return action

    def _add_root(self) -> None:
        entered = self.app.prompt("Folder whose subdirectories hold games")
        if not entered:
            return
        resolved = expand(entered)
        if not Path(resolved).is_dir():
            self.app.status = f"No folder at {resolved}"
            return
        roots = [*self.app.config["library_roots"], resolved]
        self.app.config["library_roots"] = list(dict.fromkeys(roots))
        self.app.save()
        self.app.rescan()
        self.app.status = f"Scanning {resolved}"

    def _remove_root(self) -> None:
        entered = self.app.prompt("Folder to stop scanning")
        if not entered:
            return
        resolved = expand(entered)
        remaining = [root for root in self.app.config["library_roots"] if str(root) != resolved]
        if len(remaining) == len(self.app.config["library_roots"]):
            self.app.status = f"{resolved} was not in the list"
            return
        self.app.config["library_roots"] = remaining
        self.app.save()
        self.app.rescan()
        self.app.status = f"No longer scanning {resolved}"

    def _build(self) -> list[Setting]:
        config = self.app.config
        return [
            Setting(
                "Proton build",
                "The Proton runtime every game is launched with.",
                lambda: str(config["proton_path"]),
                self._edit_path("proton_path", "Path to a Proton build"),
                lambda: "linux",
            ),
            Setting(
                "umu runner",
                "umu supplies the Steam Linux Runtime container Proton needs.",
                lambda: str(config["umu_path"]),
                self._edit_path("umu_path", "Path to umu-run"),
                lambda: "linux",
            ),
            Setting(
                "Library folders",
                "Each subdirectory of these folders is scanned for an executable.",
                lambda: f"{len(config['library_roots'])} folders",
                self._add_root,
                lambda: "text",
            ),
            Setting(
                "Stop scanning a folder",
                "Remove a folder from the scan list.",
                lambda: ", ".join(str(root) for root in config["library_roots"]) or "none",
                self._remove_root,
                lambda: "text",
            ),
            Setting(
                "Presentation",
                "Native Wayland skips XWayland. Frame pacing differs between the two.",
                self._state("enable_wayland", False, "native Wayland", "XWayland"),
                self._toggle("enable_wayland", False),
                self._role("enable_wayland", False),
            ),
            Setting(
                "gamemode",
                "Applies gamemode's scheduling changes. Off silences its dlopen warnings.",
                self._state("use_gamemode", True, "on", "off"),
                self._toggle("use_gamemode", True),
                self._role("use_gamemode", True),
            ),
            Setting(
                "Spread across all CPUs",
                "Keeps game threads on every core, undoing masks a game sets itself.",
                self._state("enforce_all_cpus", True, "on", "off"),
                self._toggle("enforce_all_cpus", True),
                self._role("enforce_all_cpus", True),
            ),
        ]

    # ---- drawing ------------------------------------------------------------

    def draw(self) -> Rect:
        inner = self.paint.frame(letterspace("SETTINGS"), str(self.app.path), KEYS)
        if inner.height < 4:
            return inner

        panes = layout.split(inner, min_list=22, max_list=34)
        self.paint.rows(panes.items, [setting.label for setting in self.settings], self.cursor)

        if panes.split and panes.detail and panes.divider_x is not None:
            self.paint.divider(panes.divider_x, inner.top, inner.height - 1)
            self._draw_detail(panes.detail)

        self.paint.status(inner, self.app.status)
        return inner

    def _draw_detail(self, area: Rect) -> None:
        chosen = self.settings[self.cursor]
        self.paint.text(area.top, area.left, fit(chosen.label, area.width), area.width, "text", bold=True)
        self.paint.text(
            area.top + 2,
            area.left,
            shorten_path(chosen.value(), area.width, self.paint.glyph("ellipsis")),
            area.width,
            chosen.role(),
        )
        self.paint.section(area.top + 4, area.left, area.width, "about")
        for offset, line in enumerate(wrap(chosen.detail, area.width)):
            if area.top + 5 + offset > area.bottom:
                break
            self.paint.text(area.top + 5 + offset, area.left, line, area.width, "label")

    def handle(self, key: int) -> bool:
        if keys.is_leave(key):
            return False
        if keys.is_down(key):
            self.cursor = (self.cursor + 1) % len(self.settings)
        elif keys.is_up(key):
            self.cursor = (self.cursor - 1) % len(self.settings)
        elif keys.is_confirm(key) or key == ord(" "):
            self.settings[self.cursor].activate()
        return True
