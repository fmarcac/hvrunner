"""Value types shared across the package."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .constants import CUSTOM_SOURCE, WINDOWS_SUFFIXES


@dataclass(frozen=True)
class Game:
    name: str
    source: str
    install_dir: str
    executable: str = ""
    # The Steam application id to run under. Launch configuration, never
    # identity: key must not consult it, or every game sharing an id would
    # collide on one favourite key.
    steam_appid: str = ""
    # A Proton build for this game alone. Wine features differ between
    # builds, and a game needing one the configured build lacks has nowhere
    # else to say so. Empty means the configured build.
    proton_path: str = ""
    launch_args: tuple[str, ...] = ()
    # Environment for this game alone, applied after everything else so it
    # wins. Pairs rather than a dict because Game is frozen and hashable.
    # Without this every per title workaround meant editing the package.
    env: tuple[tuple[str, str], ...] = ()
    favorite: bool = False

    @property
    def key(self) -> str:
        return f"{self.source}:{self.executable or self.install_dir}"

    @property
    def slug(self) -> str:
        """Filesystem-safe identifier, used for log filenames."""
        cleaned = "".join(character if character.isalnum() else "-" for character in self.name.casefold())
        return "-".join(part for part in cleaned.split("-") if part) or "game"

    @property
    def windows(self) -> bool:
        """Whether this runs through Proton at all.

        A native Linux build is started directly, with no prefix and none of the
        STEAM_COMPAT names: Proton in front of an ELF binary cannot work.
        """
        return Path(self.executable).suffix.casefold() in WINDOWS_SUFFIXES


def favorite_key(executable: Path | str) -> str:
    """Build a favourites key exactly the way Game.key does."""
    return f"{CUSTOM_SOURCE}:{executable}"


class HvrunnerError(RuntimeError):
    """Every failure this package raises for the user's benefit."""
