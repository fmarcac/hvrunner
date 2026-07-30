"""Building the launch command and starting a game."""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import display
from .affinity import watcher_command
from .constants import ENFORCE_AFFINITY_ENV, RESTORE_MONITOR_ENV
from .logs import new_log_path, prune_logs
from .models import Game, HvrunnerError

# Environment names worth showing in the interface, in display order. Anything
# else hvrunner sets is either uninteresting or derivable from these.
NOTABLE_ENV = (
    "PROTONPATH",
    "WINEPREFIX",
    "MANGOHUD_CONFIG",
    "PROTON_ENABLE_WAYLAND",
    "DXVK_ENABLE_NVAPI",
    "DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS",
    "NVPRESENT_ENABLE_SMOOTH_MOTION",
)

# Names belonging to the Windows side of the compatibility layer. The interface
# colours these differently.
WINDOWS_SIDE_ENV = frozenset({
    "DXVK_ENABLE_NVAPI",
    "DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS",
    "NVPRESENT_ENABLE_SMOOTH_MOTION",
    "WINEPREFIX",
    "WINEDEBUG",
})


@dataclass(frozen=True)
class LaunchPlan:
    command: list[str]
    environment: dict[str, str] = field(repr=False)
    prefix: Path
    prefix_ready: bool

    def notable_environment(self) -> list[tuple[str, str]]:
        return [(name, self.environment[name]) for name in NOTABLE_ENV if name in self.environment]


@dataclass(frozen=True)
class LaunchResult:
    pid: int
    log_path: Path


def reap_children_automatically() -> None:
    """Let the kernel reap exited children.

    start_new_session does not reparent, so without this every launched game and
    every finished affinity watcher stays a zombie for the lifetime of the UI.
    """
    with contextlib.suppress(ValueError, OSError, AttributeError):
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)


def _require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise HvrunnerError(f"{label} is unavailable: {path}")
    return path


def _resolve_proton(config: dict[str, Any]) -> Path:
    configured = Path(str(config["proton_path"])).expanduser()
    proton = configured.parent if configured.name == "proton" else configured
    if not (proton / "proton").is_file() or not (proton / "toolmanifest.vdf").is_file():
        raise HvrunnerError(f"Proton runtime is unavailable: {proton}")
    return proton


def prefix_path(game: Game, config: dict[str, Any]) -> Path:
    return Path(game.install_dir) / str(config["custom_prefix_name"])


def _game_environment(executable: Path, install_dir: str, prepare: bool) -> dict[str, str]:
    """Per title workarounds, keyed off the executable name."""
    # Prefix match rather than equality: the folder also ships
    # ACBlackFlag_Plus.exe, and an exact comparison would silently drop this
    # environment for that variant.
    if not executable.stem.casefold().startswith("acblackflag"):
        return {}
    environment = {
        "DXVK_ENABLE_NVAPI": "1",
        # Native DLSS frame generation and Smooth Motion must not run together.
        "NVPRESENT_ENABLE_SMOOTH_MOTION": "0",
        "DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS": "DLSSIndicator=0,DLSSGIndicator=0",
    }
    if os.environ.get("ACBF_VERIFY_DLSS") == "1":
        log_path = Path(install_dir) / "logs"
        if prepare:
            try:
                log_path.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                raise HvrunnerError(f"cannot create {log_path}: {error}") from error
        environment.update({
            "DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS": "DLSSIndicator=1024,DLSSGIndicator=2",
            "DXVK_NVAPI_LOG_LEVEL": "info",
            "DXVK_NVAPI_LOG_PATH": str(log_path),
        })
    return environment


def plan(game: Game, config: dict[str, Any], *, prepare: bool = False) -> LaunchPlan:
    """Work out exactly what would run.

    With prepare left false this touches nothing on disk, so the interface can
    show a live preview as the cursor moves.
    """
    proton = _resolve_proton(config)
    umu = _require_file(Path(str(config["umu_path"])).expanduser(), "umu")
    executable = _require_file(Path(game.executable), "game executable")
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

    environment = os.environ.copy()
    environment.update({
        "GAMEID": "0",
        "PROTONPATH": str(proton),
        "WINEPREFIX": str(prefix),
        "WINEDEBUG": "-all",
        "PROTON_USE_XALIA": "0",
        "DISABLE_GAMESCOPE_WSI": "1",
        "MANGOHUD": "1",
    })
    # An explicit MANGOHUD_CONFIG in the caller's environment wins, so present
    # mode and logging can be changed for a single run without editing config.
    environment["MANGOHUD_CONFIG"] = os.environ.get("MANGOHUD_CONFIG") or str(config["mangohud_config"])
    environment.update(_game_environment(executable, game.install_dir, prepare))

    if config.get("enable_wayland"):
        environment["PROTON_ENABLE_WAYLAND"] = "1"
    else:
        environment.pop("PROTON_ENABLE_WAYLAND", None)

    extra_env = config.get("extra_env") or {}
    if isinstance(extra_env, dict):
        for name, value in extra_env.items():
            environment[str(name)] = str(value)

    command = [mangohud, str(umu), str(executable), *game.launch_args]
    if config.get("use_gamemode", True):
        gamemoderun = shutil.which("gamemoderun")
        if gamemoderun:
            command.insert(0, gamemoderun)
    return LaunchPlan(command=command, environment=environment, prefix=prefix, prefix_ready=prefix_ready)


def build_command(game: Game, config: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    prepared = plan(game, config, prepare=True)
    return prepared.command, prepared.environment


def _drop_to_native_scale(config: dict[str, Any]) -> str | None:
    """Set the output to scale 1, returning the spec that restores it.

    Returns None when nothing was changed, which is also what the caller wants
    when hyprctl is absent or the output is already unscaled.
    """
    if not config.get("native_scale") or not display.available():
        return None
    monitor = display.focused_monitor()
    if monitor is None or not monitor.scaled:
        return None
    restore = monitor.spec(monitor.scale)
    if not display.apply(monitor.spec(1.0)):
        return None
    return restore


def launch(game: Game, config: dict[str, Any]) -> LaunchResult:
    prepared = plan(game, config, prepare=True)
    log_path = new_log_path(game)
    restore_monitor = _drop_to_native_scale(config)
    try:
        handle = log_path.open("w", buffering=1)
    except OSError as error:
        raise HvrunnerError(f"cannot open log {log_path}: {error}") from error
    try:
        handle.write(f"$ {' '.join(prepared.command)}\n")
        # Child output goes to the log rather than the terminal the interface is
        # drawing on, which is what stops the interleaved output.
        process = subprocess.Popen(
            prepared.command,
            cwd=game.install_dir,
            env=prepared.environment,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError as error:
        if restore_monitor:
            display.apply(restore_monitor)
        raise HvrunnerError(f"cannot start {game.name}: {error}") from error
    finally:
        # Popen duplicated the descriptor, so this copy is no longer needed.
        handle.close()

    enforce = bool(config.get("enforce_all_cpus", True))
    # The supervisor is also what restores the output scale, so it has to run
    # whenever either job is outstanding.
    if enforce or restore_monitor:
        supervisor_env = os.environ.copy()
        supervisor_env[ENFORCE_AFFINITY_ENV] = "1" if enforce else "0"
        if restore_monitor:
            supervisor_env[RESTORE_MONITOR_ENV] = restore_monitor
        try:
            subprocess.Popen(
                watcher_command(Path(game.executable).name, game.install_dir),
                env=supervisor_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as error:
            # Without the supervisor the scale would never come back.
            if restore_monitor:
                display.apply(restore_monitor)
            raise HvrunnerError(f"{game.name} started, but the supervisor did not: {error}") from error
    prune_logs()
    return LaunchResult(pid=process.pid, log_path=log_path)
