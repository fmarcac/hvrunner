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

# Deliberately not the "full" preset: full enables media_player, which polls
# playerctld and logs an error per frame when no MPRIS player is active. The
# user's own ~/.config/MangoHud/MangoHud.conf supplies the display options.
#
# mailbox rather than the application's choice: a compositor that has to rescale
# a fullscreen surface holds a swapchain image while it does so, and with only
# two images the game blocks on acquire and serialises on the compositor. A third
# image lets it work ahead. Measured at 57 to 113 fps on an otherwise unchanged
# setup, with the GPU at 52% both before and after.
DEFAULT_MANGOHUD_CONFIG = "toggle_hud=Shift_R+F12,vulkan_present_mode=mailbox"

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
