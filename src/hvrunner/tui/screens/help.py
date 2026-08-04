"""Key reference."""

from __future__ import annotations

from ..text import fit, letterspace
from ..widgets import Rect
from .base import Screen

SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "library",
        [
            ("enter", "run the selected game"),
            ("j k", "move the cursor"),
            ("f", "favourite, which sorts it to the top"),
            ("e", "edit, rename or delete the selected game"),
            ("a", "add an executable by path"),
            ("i", "install from a Windows installer"),
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

KEY_COLUMN = 11


class HelpScreen(Screen):
    def draw(self) -> Rect:
        inner = self.paint.frame(letterspace("KEYS"), "", "any key returns")
        row = inner.top + 1
        for heading, entries in SECTIONS:
            if row >= inner.bottom:
                break
            self.paint.section(row, inner.left + 1, inner.width - 2, heading)
            row += 1
            for combination, description in entries:
                if row >= inner.bottom:
                    break
                self.paint.text(row, inner.left + 2, combination.ljust(KEY_COLUMN), KEY_COLUMN, "linux")
                width = inner.width - KEY_COLUMN - 4
                self.paint.text(row, inner.left + KEY_COLUMN + 3, fit(description, width), width, "text")
                row += 1
            row += 1
        return inner

    def handle(self, key: int) -> bool:
        return False
