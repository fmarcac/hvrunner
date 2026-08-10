"""Tunables and paths. Nothing here imports the rest of the package."""

from __future__ import annotations

import os
import re
from pathlib import Path

APP_NAME = "hvrunner"

DEFAULT_COMPAT_ROOT = Path.home() / ".local/share/Steam"
DEFAULT_PROTON = DEFAULT_COMPAT_ROOT / "compatibilitytools.d/Proton-GE11-1-LinUwUx/proton"
DEFAULT_UMU = Path("/usr/bin/umu-run")
DEFAULT_CUSTOM_ROOT = Path("/mnt/data/games")

# Single source of truth for the source label. Game.key derives from it, so any
# favourite key built by hand must use this same constant or favourites silently
# stop matching after a rescan.
CUSTOM_SOURCE = "Custom"

# Spacewar, the Steam application anything that is not a Steam game is
# conventionally run as. It gives a game a real SteamAppId without pretending
# to be a title the user does not own.
SPACEWAR_APPID = "480"

# Empty on purpose, so MANGOHUD_CONFIG is left unset.
#
# MANGOHUD_CONFIG in the environment REPLACES ~/.config/MangoHud/MangoHud.conf,
# it does not merge with it. Setting it here threw away the user's whole HUD
# layout. Leaving it unset means MangoHud reads their file, which is where HUD
# content belongs. It also avoids the "full" preset, whose media_player module
# logs an error on every poll when no MPRIS player is running.
DEFAULT_MANGOHUD_CONFIG = ""

# Wine's err channel is the only place a fatal startup failure is reported. A
# DLL whose DllMain faults produces one err:module:loader_init line naming it
# and nothing else, so "-all" left a game that died on startup looking exactly
# like one that launched: a log full of gamemode noise and no reason. fixme is
# the genuinely noisy channel and none of it is actionable, so it stays off.
DEFAULT_WINEDEBUG = "err+all,fixme-all"

# How long after a launch a vanished process still counts as a failed start
# rather than a game the user played and quit. Prefix creation and shader
# compilation happen before the window appears, so this only has to outlast the
# point at which the loader would have given up.
LAUNCH_SETTLE_SECONDS = 20.0

# Names passed to the supervising process so it can undo what launch changed.
RESTORE_MONITOR_ENV = "HVRUNNER_RESTORE_MONITOR"
ENFORCE_AFFINITY_ENV = "HVRUNNER_ENFORCE_AFFINITY"

# How deep to look for a game executable. Unreal-style layouts bury the binary
# in Binaries/Win64.
EXE_SEARCH_DEPTH = 3

INSTALLER_PATTERN = re.compile(r"(unins|setup|install|crash|redist|vcredist|dxsetup|touchup)", re.I)

# affinity watcher timings. The startup window must survive first-launch prefix
# creation and shader compilation; the absence window must survive a game that
# re-execs itself or hands off between processes.
AFFINITY_STARTUP_TIMEOUT = 600.0
AFFINITY_ABSENCE_TIMEOUT = 30.0
AFFINITY_POLL_INTERVAL = 0.25

# Linux truncates /proc/<pid>/comm to 15 characters plus a NUL.
COMM_MAX_LENGTH = 15

LOG_KEEP = 20
LOG_TAIL_BYTES = 256 * 1024

# Total the log directory may hold. err+all lets a single launch write far more
# than the old -all ever did, and twenty unbounded logs is a lot of disk.
#
# This bounds what is kept, not what is being written: the game inherits the log
# descriptor and writes to it directly, so hvrunner never sees those bytes and
# cannot stop them. Capping the live file would mean draining a pipe in a
# process that outlives the interface, which the supervisor does not do today.
LOG_BUDGET_BYTES = 64 * 1024 * 1024


def state_dir() -> Path:
    root = os.environ.get("XDG_STATE_HOME")
    base = Path(root).expanduser() if root else Path.home() / ".local/state"
    return base / APP_NAME


def log_dir() -> Path:
    return state_dir() / "logs"


def config_path() -> Path:
    configured = os.environ.get("HVRUNNER_CONFIG")
    if configured:
        return Path(configured).expanduser()
    root = os.environ.get("XDG_CONFIG_HOME")
    base = Path(root).expanduser() if root else Path.home() / ".config"
    return base / APP_NAME / "config.json"
