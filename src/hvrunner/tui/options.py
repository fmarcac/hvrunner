"""One selectable line of a list-and-detail screen.

The settings screen and the entry editor carried a dataclass each, identical
except that one of them had a colour hook. Two names for one thing is how they
drift apart, so there is one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


def _plain() -> str:
    return "text"


@dataclass(frozen=True)
class Option:
    label: str
    #: Prose shown under the value. Wrapped by the detail pane.
    detail: str
    value: Callable[[], str]
    activate: Callable[[], None]
    #: Colour role for the value, so a setting can show that it is on.
    role: Callable[[], str] = _plain
