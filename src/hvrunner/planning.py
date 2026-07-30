"""Working out exactly what a launch would do, without doing it."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import environment as environment_module
from .environment import NOTABLE_ENV
from .models import Game, HvrunnerError


@dataclass(frozen=True)
class LaunchPlan:
    command: list[str]
    environment: dict[str, str] = field(repr=False)
    prefix: Path
    prefix_ready: bool

    def notable_environment(self) -> list[tuple[str, str]]:
        return [(name, self.environment[name]) for name in NOTABLE_ENV if name in self.environment]


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise HvrunnerError(f"{label} is unavailable: {path}")
    return path


def resolve_proton(config: dict[str, Any]) -> Path:
    configured = Path(str(config["proton_path"])).expanduser()
    proton = configured.parent if configured.name == "proton" else configured
    if not (proton / "proton").is_file() or not (proton / "toolmanifest.vdf").is_file():
        raise HvrunnerError(f"Proton runtime is unavailable: {proton}")
    return proton


def prefix_path(game: Game, config: dict[str, Any]) -> Path:
    return Path(game.install_dir) / str(config["custom_prefix_name"])


def plan(game: Game, config: dict[str, Any], *, prepare: bool = False) -> LaunchPlan:
    """Work out exactly what would run.

    With prepare left false this touches nothing on disk, so the interface can
    show a live preview as the cursor moves.
    """
    proton = resolve_proton(config)
    umu = require_file(Path(str(config["umu_path"])).expanduser(), "umu")
    executable = require_file(Path(game.executable), "game executable")
    mangohud = shutil.which("mangohud")
    if not mangohud:
        raise HvrunnerError("MangoHud is unavailable")

    prefix = prefix_path(game, config)
    prefix_ready = prefix.is_dir()
    if prepare and not prefix_ready:
        try:
            prefix.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise HvrunnerError(f"cannot create prefix {prefix}: {error}") from error

    built = environment_module.build(game, config, proton, prefix, prepare=prepare)

    command = [mangohud, str(umu), str(executable), *game.launch_args]
    if config.get("use_gamemode", True):
        gamemoderun = shutil.which("gamemoderun")
        if gamemoderun:
            command.insert(0, gamemoderun)
    return LaunchPlan(command=command, environment=built, prefix=prefix, prefix_ready=prefix_ready)


def build_command(game: Game, config: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    prepared = plan(game, config, prepare=True)
    return prepared.command, prepared.environment
