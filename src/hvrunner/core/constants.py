"""Tunables and paths. Nothing here imports the rest of the package."""

from __future__ import annotations

import os
import re
from pathlib import Path

APP_NAME = "hvrunner"

DEFAULT_COMPAT_ROOT = Path.home() / ".local/share/Steam"
DEFAULT_PROTON = DEFAULT_COMPAT_ROOT / "compatibilitytools.d/Proton-GE11-1-LinUwUx/proton"
DEFAULT_CUSTOM_ROOT = Path("/mnt/data/games")

# Single source of truth for the source label. Game.key derives from it, so any
# favourite key built by hand must use this same constant or favourites silently
# stop matching after a rescan.
CUSTOM_SOURCE = "Custom"

# What Proton is asked to run. Anything else is a native Linux program and is
# started directly, because putting Proton in front of an ELF binary is how a
# Linux port becomes unlaunchable.
#
# .bat and .cmd need cmd.exe in front of them and .msi needs msiexec: Wine will
# not infer either. planning.runner is where that is decided.
WINDOWS_SUFFIXES = frozenset({".exe", ".bat", ".cmd", ".msi"})
SCRIPT_SUFFIXES = frozenset({".bat", ".cmd"})
INSTALLER_SUFFIXES = frozenset({".msi"})

# Preferred order when a folder offers more than one. A real game ships an .exe;
# the rest are launchers and setup wrappers around one.
SUFFIX_RANK = {".exe": 0, ".cmd": 1, ".bat": 1, ".msi": 2}

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
# in Binaries/Win64, and a repack adds a folder above that, which is what the
# fourth level is for. The scan reads directory entries without stat'ing them,
# so the extra level costs a scandir per folder rather than a walk of stats.
EXE_SEARCH_DEPTH = 4

# A native Linux game keeps its launcher at the top, so this stays shallow: it
# is a fallback for folders holding no Windows program at all, and the deeper it
# goes the more of the game's own tooling it would offer as candidates.
NATIVE_SEARCH_DEPTH = 2

# Names that are not the game. Matched anywhere in the filename, which is safe
# because select_executable falls back to the unfiltered list when everything
# would be filtered out.
INSTALLER_PATTERN = re.compile(
    r"(unins|setup|install|crash|redist|vcredist|dxsetup|touchup|prereq"
    r"|easyanticheat|battleye|dotnet|directx|oalinst|dxwebsetup|benchmark)",
    re.I,
)

# affinity watcher timings. The startup window must survive first-launch prefix
# creation and shader compilation; the absence window must survive a game that
# re-execs itself or hands off between processes.
AFFINITY_STARTUP_TIMEOUT = 600.0
AFFINITY_ABSENCE_TIMEOUT = 30.0
AFFINITY_POLL_INTERVAL = 0.25

# Once the game has been found, the watcher is only there to undo a mask the
# game sets on itself later and to notice the exit. Neither needs a quarter of a
# second: the scan walks every process on the machine, and at 4 Hz that was
# costing several percent of a core for as long as the game ran.
AFFINITY_SETTLED_INTERVAL = 2.0

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

# Long enough for a cold prefix update, short enough that a wedged wineserver
# cannot hold a launch open forever.
REGISTER_TIMEOUT = 120.0

# hyprctl answers immediately or not at all.
HYPRCTL_TIMEOUT = 5.0


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
