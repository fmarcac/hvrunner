"""Value types shared across the package."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .constants import CUSTOM_SOURCE


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

    @property
    def slug(self) -> str:
        """Filesystem-safe identifier, used for log filenames."""
        cleaned = "".join(character if character.isalnum() else "-" for character in self.name.casefold())
        return "-".join(part for part in cleaned.split("-") if part) or "game"


def favorite_key(executable: Path | str) -> str:
    """Build a favourites key exactly the way Game.key does."""
    return f"{CUSTOM_SOURCE}:{executable}"


class HvrunnerError(RuntimeError):
    """Every failure this package raises for the user's benefit."""
