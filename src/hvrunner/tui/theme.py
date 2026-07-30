"""Colour and glyphs.

The palette is Nord, matching the MangoHud overlay this launcher starts, so the
two read as one tool.

Colour carries meaning rather than decoration. hvrunner runs Windows binaries on
Linux, and the interface says which side of that layer a thing belongs to:
LINUX for the Proton and umu side, WINDOWS for the executable and its DXVK and
NVAPI settings.
"""

from __future__ import annotations

import curses
import locale

# Nord, https://www.nordtheme.com, mapped to the nearest fixed entries of the
# 256 colour cube.
#
# Redefining palette entries with init_color would give exact values, but it
# mutates the terminal's own palette, does not reliably survive in every
# terminal, and can leak into other programs. Fixed indices touch nothing.
_ROLES: dict[str, int] = {
    "text": 253,       # nord4  d8dee9
    "rule": 59,        # nord3  4c566a
    "label": 110,      # nord9  81a1c1
    "linux": 116,      # nord8  88c0d0, also selection and headings
    "windows": 139,    # nord15 b48ead
    "favourite": 222,  # nord13 ebcb8b
    "ok": 150,         # nord14 a3be8c
    "warn": 173,       # nord12 d08770
    "error": 131,      # nord11 bf616a
}

_FALLBACK: dict[str, int] = {
    "text": curses.COLOR_WHITE,
    "rule": curses.COLOR_BLUE,
    "label": curses.COLOR_BLUE,
    "linux": curses.COLOR_CYAN,
    "windows": curses.COLOR_MAGENTA,
    "favourite": curses.COLOR_YELLOW,
    "ok": curses.COLOR_GREEN,
    "warn": curses.COLOR_YELLOW,
    "error": curses.COLOR_RED,
}

_UNICODE = {
    "h": "─",
    "v": "│",
    "tl": "╭",
    "tr": "╮",
    "bl": "╰",
    "br": "╯",
    "tee_down": "┬",
    "tee_up": "┴",
    "bar": "▌",
    "star": "★",
    "dot": "·",
    "arrow": "→",
    "ellipsis": "…",
}

_ASCII = {
    "h": "-",
    "v": "|",
    "tl": "+",
    "tr": "+",
    "bl": "+",
    "br": "+",
    "tee_down": "+",
    "tee_up": "+",
    "bar": "|",
    "star": "*",
    "dot": ".",
    "arrow": ">",
    "ellipsis": "...",
}


class Theme:
    def __init__(self) -> None:
        self._pairs: dict[str, int] = {}
        self.colored = False
        self.glyphs = _UNICODE if self._unicode_ok() else _ASCII

    @staticmethod
    def _unicode_ok() -> bool:
        try:
            encoding = locale.getpreferredencoding(False) or ""
        except (ValueError, LookupError):
            return False
        return "utf" in encoding.casefold()

    def setup(self) -> None:
        if not curses.has_colors():
            return
        curses.start_color()
        try:
            curses.use_default_colors()
            background = -1
        except curses.error:
            background = curses.COLOR_BLACK

        wide = curses.COLORS >= 256
        for index, (name, cube) in enumerate(_ROLES.items()):
            foreground = cube if wide else _FALLBACK[name]
            try:
                curses.init_pair(index + 1, foreground, background)
            except curses.error:
                continue
            self._pairs[name] = index + 1
        self.colored = bool(self._pairs)

    def attr(self, role: str, *, bold: bool = False, dim: bool = False, reverse: bool = False) -> int:
        attribute = curses.color_pair(self._pairs.get(role, 0)) if self.colored else 0
        if not self.colored:
            # Monochrome terminals get emphasis instead of hue.
            if role in {"linux", "favourite"}:
                bold = True
            elif role in {"rule", "label"}:
                dim = True
        if bold:
            attribute |= curses.A_BOLD
        if dim:
            attribute |= curses.A_DIM
        if reverse:
            attribute |= curses.A_REVERSE
        return attribute

    def glyph(self, name: str) -> str:
        return self.glyphs.get(name, "?")
