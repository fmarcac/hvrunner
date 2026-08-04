"""Running a Windows installer into a fresh game folder."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import CUSTOM_SOURCE, INSTALLER_PATTERN
from .environment import build as build_environment
from .library import normalise, rank_executables
from .logs import new_log_path
from .models import Game, HvrunnerError
from .planning import prefix_path, require_file, resolve_proton

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
    """The bare umu command that runs source inside target's prefix.

    No MangoHud and no gamemode: a HUD over a setup wizard is noise, and
    gamemode's scheduling changes are meaningless for a process that exits in a
    minute.
    """
    proton = resolve_proton(config)
    umu = require_file(Path(str(config["umu_path"])).expanduser(), "umu")
    require_file(source, "installer")
    game = _as_game(source, target)
    prefix = prefix_path(game, config)
    try:
        prefix.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise HvrunnerError(f"cannot create prefix {prefix}: {error}") from error
    environment = build_environment(game, config, proton, prefix, prepare=True)
    environment.pop("MANGOHUD", None)
    return [str(umu), str(source)], environment, prefix


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
            cwd=str(target),
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
    """True while the installer is alive.

    Popen.wait cannot answer this: cli.main sets SIGCHLD to SIG_IGN so the
    kernel reaps children itself, after which wait raises ChildProcessError and
    poll never reports a status.
    """
    return Path(f"/proc/{run.process.pid}").exists()


def discover(prefix: Path, name: str) -> list[Path]:
    """Candidate game binaries inside a finished prefix, best first."""
    drive = prefix / "pfx" / "drive_c"
    if not drive.is_dir():
        return []
    found: list[Path] = []

    def walk(directory: Path, depth: int) -> None:
        if depth > DISCOVER_DEPTH:
            return
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            try:
                if entry.is_file():
                    if entry.suffix.lower() == ".exe" and not INSTALLER_PATTERN.search(entry.name):
                        found.append(entry)
                elif entry.is_dir() and entry.name.casefold() not in SKIP_DIRECTORIES:
                    walk(entry, depth + 1)
            except OSError:
                continue

    walk(drive, 0)
    return rank_executables(found, drive, normalise(name))
