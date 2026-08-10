"""Asking for a path, with the file browser behind tab.

The prompt cannot open the browser itself: the browser is a screen, screens do
not import one another, and the prompt is not a screen. This is where the two
meet.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core import browsing
from ..core.browsing import Want
from ..core.config import expand
from . import prompt as prompt_module
from .screens import BrowseScreen

if TYPE_CHECKING:
    from .app import App


def browse_root(config: dict[str, Any]) -> Path:
    """Where a browse with nothing typed starts.

    A library folder is the answer nearly every time, so offering the whole
    filesystem first would just be a directory to walk out of.
    """
    for root in config["library_roots"]:
        candidate = Path(expand(str(root)))
        if candidate.is_dir():
            return candidate
    return Path.home()


def ask_for_path(app: App, label: str, want: Want, initial: str = "") -> str | None:
    """Ask for a path, with tab opening the browser.

    Leaving the browser without picking returns to the field with what was
    typed still in it.
    """
    typed = initial
    while True:
        answer = prompt_module.ask(app.screen, app.theme, label, typed, browsable=True)
        if answer is None:
            if app.screen.getmaxyx()[1] < prompt_module.MINIMUM_WIDTH:
                app.status = "Terminal is too small for that"
            return None
        if isinstance(answer, str):
            return answer
        typed = answer.text
        start = browsing.start_directory(typed, browse_root(app.config))
        picked = BrowseScreen(app, start, want).choose()
        if picked is not None:
            return str(picked)
