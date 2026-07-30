"""The launch preview.

Choosing a game means choosing a Proton build, a prefix, a MangoHud
configuration and a set of DXVK overrides, and none of that is visible from a
filename. This pane shows the argv and the environment that will actually be
used, so the choice is inspectable before anything starts.
"""

from __future__ import annotations

from pathlib import Path

from ...environment import WINDOWS_SIDE_ENV
from ...models import Game, HvrunnerError
from ...planning import plan
from ..text import fit
from ..widgets import Painter, Rect


def draw(paint: Painter, area: Rect, game: Game, config: dict) -> None:
    if area.width < 12 or area.height < 2:
        return
    row = area.top
    paint.text(row, area.left, fit(Path(game.executable).name, area.width), area.width, "windows", bold=True)
    row += 1

    try:
        prepared = plan(game, config)
    except HvrunnerError as error:
        paint.text(row + 1, area.left, fit(str(error), area.width), area.width, "error")
        return

    if prepared.prefix_ready:
        paint.text(row, area.left, "prefix ready", area.width, "ok")
    else:
        paint.text(row, area.left, "first run, expect a long start", area.width, "warn")
    row += 2

    row = _draw_command(paint, area, row, prepared.command)
    row = _draw_environment(paint, area, row, prepared.notable_environment())
    _draw_arguments(paint, area, row, game.launch_args)


def _draw_command(paint: Painter, area: Rect, row: int, command: list[str]) -> int:
    if row >= area.bottom:
        return row
    paint.section(row, area.left, area.width, "command")
    row += 1
    # Each wrapper indents, so the layering is visible: gamemode wraps MangoHud
    # wraps umu wraps the Windows binary.
    for depth, part in enumerate(command):
        if row > area.bottom - 1:
            break
        indent = min(depth * 2, max(0, area.width - 8))
        name = Path(part).name if part.startswith("/") else part
        role = "windows" if name.casefold().endswith(".exe") else "linux"
        paint.text(row, area.left + indent, fit(name, area.width - indent), area.width - indent, role)
        row += 1
    return row + 1


def _draw_environment(paint: Painter, area: Rect, row: int, entries: list[tuple[str, str]]) -> int:
    if row >= area.bottom or not entries:
        return row
    paint.section(row, area.left, area.width, "environment")
    row += 1
    # One shared label column, otherwise the values sit ragged.
    column = min(max(len(name) for name, _ in entries) + 1, max(1, area.width // 2))
    for name, value in entries:
        if row > area.bottom:
            break
        shown = Path(value).name if value.startswith("/") else value
        role = "windows" if name in WINDOWS_SIDE_ENV else "linux"
        paint.field(row, area.left, area.width, name, shown, role, name_width=column)
        row += 1
    return row


def _draw_arguments(paint: Painter, area: Rect, row: int, arguments: tuple[str, ...]) -> None:
    if not arguments or row + 1 >= area.bottom:
        return
    row += 1
    paint.section(row, area.left, area.width, "arguments")
    paint.text(row + 1, area.left, fit(" ".join(arguments), area.width), area.width, "text")
