"""Getting a Proton prefix into a state a game can actually run in.

Everything here is idempotent and cheap to repeat, because it runs before every
launch rather than only when the prefix is new. The expensive step is guarded by
a file read, so a prefix that is already correct costs one open.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .models import HvrunnerError

# Where Wine looks a WinRT class up before activating it.
ACTIVATABLE = "Software\\Microsoft\\WindowsRuntime\\ActivatableClassId"

# Classes Wine implements but never registers, and the DLL that serves each.
#
# coremessaging.dll carries all four DispatcherQueue names, but its self
# registration script only names DispatcherQueueController. A C++/WinRT plugin
# asking for the plain class therefore gets a failed RoGetActivationFactory,
# check_hresult throws, and the game dies during startup with an unhandled
# 0xe06d7363 and nothing in the log but "Failed to find library for".
WINRT_CLASSES = {
    "Windows.System.DispatcherQueue": "C:\\windows\\system32\\coremessaging.dll",
}

# Long enough for a cold prefix update, short enough that a wedged wineserver
# cannot hold a launch open forever.
REGISTER_TIMEOUT = 120.0


def create(prefix: Path) -> None:
    """Make sure the prefix directory exists before anything is asked of it."""
    try:
        prefix.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise HvrunnerError(f"cannot create prefix {prefix}: {error}") from error
    if not prefix.is_dir():
        raise HvrunnerError(f"prefix is not a directory: {prefix}")


def link_pfx(prefix: Path) -> None:
    """Give the prefix the layout Proton expects.

    Proton takes STEAM_COMPAT_DATA_PATH and uses <path>/pfx as the WINEPREFIX,
    so the prefix has to contain a "pfx" pointing back at itself. Without the
    link Proton silently builds a second prefix one level down and the game
    opens with none of its saves. installer.discover walks the same path.
    """
    link = prefix / "pfx"
    if link.is_symlink() or link.exists():
        return
    try:
        link.symlink_to(".")
    except OSError as error:
        raise HvrunnerError(f"cannot link {link}: {error}") from error


def wine_binary(proton: Path) -> Path:
    return proton / "files" / "bin" / "wine"


def marker(name: str) -> str:
    """How a class key is spelled inside system.reg.

    Wine escapes every backslash when it writes the file, so the key that reads
    Software\\Microsoft\\... in a reg command is stored doubled throughout.
    Escaping only the last separator matches nothing at all.
    """
    return f"[{ACTIVATABLE}\\{name}]".replace("\\", "\\\\")


def registered(prefix: Path, name: str) -> bool:
    """Whether system.reg already carries an activation entry for a class.

    A prefix with no system.reg has not been built yet, and Proton writes the
    stock registrations when it builds one, so there is nothing to add and
    nothing to report.
    """
    try:
        text = (prefix / "system.reg").read_text(errors="replace")
    except OSError:
        return True
    return marker(name) in text


def missing(prefix: Path) -> dict[str, str]:
    return {name: dll for name, dll in WINRT_CLASSES.items() if not registered(prefix, name)}


def register(prefix: Path, proton: Path, name: str, dll: str) -> str:
    """Add one activation entry, returning a line for the log.

    Never raises. A prefix that cannot be repaired should still get its launch
    attempted, because the class may be one this particular game never asks for.
    """
    wine = wine_binary(proton)
    command = [
        str(wine),
        "reg",
        "add",
        f"HKLM\\{ACTIVATABLE}\\{name}",
        "/v",
        "DllPath",
        "/d",
        dll,
        "/f",
    ]
    if not wine.is_file():
        return f"cannot register {name}: no wine at {wine}"
    try:
        finished = subprocess.run(
            command,
            env={"WINEPREFIX": str(prefix), "WINEDEBUG": "-all", "PATH": "/usr/bin:/bin"},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=REGISTER_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return f"cannot register {name}: {error}"
    if finished.returncode != 0:
        return f"registering {name} exited {finished.returncode}"
    return f"registered {name} -> {dll}"


def repair(prefix: Path, proton: Path) -> list[str]:
    """Register whatever Wine left out, reporting what was done.

    Runs before the game rather than after, because Wine keeps the registry in
    wineserver and flushes it on exit: writing while the game holds the prefix
    would be undone the moment it quits.
    """
    return [register(prefix, proton, name, dll) for name, dll in missing(prefix).items()]
