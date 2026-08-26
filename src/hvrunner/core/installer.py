"""Running a Windows installer into a fresh game folder."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import prefix as prefix_module
from .constants import CUSTOM_SOURCE, INSTALLER_PATTERN
from .environment import build as build_environment
from .launcher import alive, working_directory
from .library import executable_candidates, normalise, rank_executables
from .logs import new_log_path
from .models import Game, HvrunnerError
from .planning import prefix_path, require_file, resolve_proton, runner

# drive_c holds the whole Windows install, so the walk has to be bounded and the
# system trees skipped or every candidate would be a Microsoft binary.
DISCOVER_DEPTH = 6
SKIP_DIRECTORIES = frozenset({"windows", "programdata", "users"})


@dataclass(frozen=True)
class InstallRun:
    process: subprocess.Popen[bytes]
    log_path: Path
    prefix: Path
    target: Path


def prepare_target(root: Path, name: str) -> Path:
    """Create the folder the game will live in."""
    target = root / name
    if target.exists():
        raise HvrunnerError(f"{target} already exists")
    try:
        target.mkdir(parents=True)
    except OSError as error:
        raise HvrunnerError(f"cannot create {target}: {error}") from error
    return target


def _as_game(source: Path, target: Path) -> Game:
    return Game(target.name, CUSTOM_SOURCE, str(target), str(source))


def install_command(source: Path, target: Path, config: dict[str, Any]) -> tuple[list[str], dict[str, str], Path]:
    """The bare Proton command that runs source inside target's prefix.

    No MangoHud and no gamemode: a HUD over a setup wizard is noise, and
    gamemode's scheduling changes are meaningless for a process that exits in a
    minute. The prefix is built exactly as a game's is, so an installer that
    consults Steam finds the same populated client directory a game would.

    runner decides how the source is handed to Proton, so a .msi package reaches
    msiexec rather than being run as if it were a program.
    """
    proton = resolve_proton(config)
    require_file(source, "installer")
    game = _as_game(source, target)
    prefix = prefix_path(game, config)
    prefix_module.create(prefix)
    prefix_module.link_pfx(prefix)
    environment = build_environment(game, config, proton, prefix, prepare=True)
    environment.pop("MANGOHUD", None)
    return runner(proton, source), environment, prefix


def start(source: Path, target: Path, config: dict[str, Any]) -> InstallRun:
    command, environment, prefix = install_command(source, target, config)
    log_path = new_log_path(_as_game(source, target))
    try:
        handle = log_path.open("w", buffering=1)
    except OSError as error:
        raise HvrunnerError(f"cannot open log {log_path}: {error}") from error
    try:
        handle.write(f"$ {' '.join(command)}\n")
        process = subprocess.Popen(
            command,
            # The installer's own folder, for the same reason a game gets its
            # own: a multi part setup keeps its .bin and .cab files beside the
            # exe and resolves them from the working directory. The empty target
            # folder offered nothing, and the prefix decides where it installs.
            # It is also what lets cmd and msiexec be given a bare filename.
            cwd=working_directory(str(source)),
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError as error:
        raise HvrunnerError(f"cannot start installer {source}: {error}") from error
    finally:
        handle.close()
    return InstallRun(process=process, log_path=log_path, prefix=prefix, target=target)


def running(run: InstallRun) -> bool:
    """True while the installer is alive."""
    return alive(run.process.pid)


def discover(prefix: Path, name: str) -> list[Path]:
    """Candidate game binaries inside a finished prefix, best first.

    The same bounded walk the library scan uses, given the system trees to skip
    and a depth that reaches into Program Files without wandering the whole of
    drive_c.
    """
    drive = prefix / "pfx" / "drive_c"
    if not drive.is_dir():
        return []
    found = executable_candidates(drive, DISCOVER_DEPTH, SKIP_DIRECTORIES)
    playable = [path for path in found if not INSTALLER_PATTERN.search(path.name)]
    return rank_executables(playable, drive, normalise(name))
