"""Working out exactly what a launch would do, without doing it."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import electron
from . import environment as environment_module
from . import prefix as prefix_module
from .constants import INSTALLER_SUFFIXES, SCRIPT_SUFFIXES
from .environment import NOTABLE_ENV
from .models import Game, HvrunnerError

# "run", not "waitforexitandrun". The waiting verb blocks until every process in
# the prefix is gone and says nothing at all while it waits, so launching into a
# prefix that already held a game hung forever and read as a failed launch.
# launcher.launch asks the process table instead, before anything starts.
PROTON_VERB = "run"


@dataclass(frozen=True)
class LaunchPlan:
    command: list[str]
    environment: dict[str, str] = field(repr=False)
    # None for a native Linux game, which has no prefix because it has no Wine.
    prefix: Path | None
    prefix_ready: bool

    def notable_environment(self) -> list[tuple[str, str]]:
        return [(name, self.environment[name]) for name in NOTABLE_ENV if name in self.environment]


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise HvrunnerError(f"{label} is unavailable: {path}")
    return path


def resolve_proton(config: dict[str, Any], game: Game | None = None) -> Path:
    """The Proton build a game runs with.

    A game may name its own. Wine features differ between builds, and a game
    that needs one the configured build lacks would otherwise have nowhere to
    say so: Dagger Directive's C++/WinRT plugin wants a
    Windows.System.DispatcherQueue that not every build implements.

    The setting may name the build directory or the proton script inside it.
    Which one it is has to be decided by looking for the script, not by the last
    component's name: a build directory that happens to be called "proton" was
    resolved to its parent and reported as unavailable.
    """
    declared = str(game.proton_path) if game else ""
    configured = Path(declared or str(config["proton_path"])).expanduser()
    proton = configured if (configured / "proton").is_file() else configured.parent
    if not (proton / "proton").is_file() or not (proton / "toolmanifest.vdf").is_file():
        # Named as the user wrote it, not as it was resolved.
        raise HvrunnerError(f"Proton runtime is unavailable: {configured}")
    return proton


def prefix_path(game: Game, config: dict[str, Any]) -> Path:
    return Path(game.install_dir) / str(config["custom_prefix_name"])


def wrappers(config: dict[str, Any]) -> list[str]:
    """The commands the game is wrapped in, outermost first.

    Neither is required. A binary that is enabled but not installed is an
    environment fact rather than a misconfiguration, and refusing to launch over
    it is how a missing MangoHud used to make hvrunner unusable outright.
    """
    found: list[str] = []
    for name, key in (("gamemoderun", "use_gamemode"), ("mangohud", "use_mangohud")):
        if not config.get(key, True):
            continue
        located = shutil.which(name)
        if located:
            found.append(located)
    return found


def runner(proton: Path, executable: Path) -> list[str]:
    """Proton, the verb, and how this particular program has to be handed to it.

    umu used to sit in front of Proton. It assigns
    STEAM_COMPAT_CLIENT_INSTALL_PATH an empty string and never reassigns it, so
    Proton's setup_steam_files left C:\\Program Files (x86)\\Steam empty while
    still writing SteamPath and ActiveProcess into the registry. Every Steam
    facing failure this launcher had traces back to that: a genuine
    steam_api64.dll reporting Steam as not running, and OnlineFix's
    SteamOverlay64.dll failing to load GameOverlayRenderer64.dll with error 126.
    Proton run directly is given the real path and populates the prefix, and it
    still applies protonfixes.

    A batch file needs cmd.exe and an installer package needs msiexec; Wine
    infers neither. Both are given the bare filename rather than a path, because
    neither accepts a unix path for what it is asked to open and the launcher
    already starts them in the file's own folder.
    """
    command = [str(require_file(proton / "proton", "Proton")), PROTON_VERB]
    suffix = executable.suffix.casefold()
    if suffix in SCRIPT_SUFFIXES:
        return [*command, "cmd", "/c", executable.name]
    if suffix in INSTALLER_SUFFIXES:
        return [*command, "msiexec", "/i", executable.name]
    return [*command, str(executable)]


def _native_plan(game: Game, config: dict[str, Any], executable: Path) -> LaunchPlan:
    """A Linux build, started directly.

    No Proton, no prefix and none of the STEAM_COMPAT names: there is no Wine in
    this launch. The wrappers still apply, because gamemode and MangoHud are
    about the machine rather than the compatibility layer.
    """
    if not os.access(executable, os.X_OK):
        raise HvrunnerError(f"not executable, and not a Windows program: {executable}")
    # Decided from what the folder holds, not from the entry: an unpacked
    # Electron build needs these whoever is launching it.
    extra = electron.arguments(executable, game.launch_args) if electron.is_electron(executable) else []
    return LaunchPlan(
        command=[*wrappers(config), str(executable), *extra, *game.launch_args],
        environment=environment_module.native(game, config),
        prefix=None,
        prefix_ready=True,
    )


def plan(game: Game, config: dict[str, Any], *, prepare: bool = False) -> LaunchPlan:
    """Work out exactly what would run.

    With prepare left false this touches nothing on disk, so the interface can
    show a live preview as the cursor moves. With it true the prefix is brought
    into existence and given its layout, because a launch must never be the
    thing that discovers the prefix was missing.
    """
    executable = require_file(Path(game.executable), "game executable")
    if not game.windows:
        return _native_plan(game, config, executable)

    proton = resolve_proton(config, game)
    prefix = prefix_path(game, config)
    prefix_ready = prefix.is_dir()
    if prepare:
        prefix_module.create(prefix)
        prefix_module.link_pfx(prefix)

    built = environment_module.build(game, config, proton, prefix, prepare=prepare)
    command = [*wrappers(config), *runner(proton, executable), *game.launch_args]
    return LaunchPlan(command=command, environment=built, prefix=prefix, prefix_ready=prefix_ready)
