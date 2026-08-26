"""Electron games: native Linux programs that need two things of their own.

An unpacked Electron build ships its own Chromium, and Chromium makes two
assumptions that a game shipped this way usually breaks. Both are properties of
the build rather than of one title, which is why they are decided here from what
the folder contains and not written into an entry by hand.
"""

from __future__ import annotations

import stat
from pathlib import Path
from typing import Any

# What makes a native binary an Electron app rather than anything else sitting
# beside a resources folder: the packed application, plus a Chromium payload.
APPLICATION = ("resources/app.asar", "resources/app")
CHROMIUM = ("v8_context_snapshot.bin", "libffmpeg.so", "chrome-sandbox")

NO_SANDBOX = "--no-sandbox"
OZONE_HINT = "ELECTRON_OZONE_PLATFORM_HINT"


def is_electron(executable: Path) -> bool:
    """Whether this binary is the entry point of an Electron build."""
    folder = executable.parent
    if not any((folder / name).exists() for name in APPLICATION):
        return False
    return any((folder / name).is_file() for name in CHROMIUM)


def sandbox_usable(folder: Path) -> bool:
    """Whether Chromium's SUID helper is installed the way it insists on.

    It has to be owned by root and carry the setuid bit. A game unpacked into a
    library folder ships it as an ordinary file, and Chromium then aborts rather
    than falling back to anything: the renderer dies before a window exists, so
    the launch looks like a crash with nothing to explain it.
    """
    helper = folder / "chrome-sandbox"
    if not helper.is_file():
        # Nothing to be misconfigured. The namespace sandbox is used instead.
        return True
    try:
        info = helper.stat()
    except OSError:
        return False
    return info.st_uid == 0 and bool(info.st_mode & stat.S_ISUID)


def arguments(executable: Path, existing: tuple[str, ...] = ()) -> list[str]:
    """Arguments this build needs, minus anything the entry already passes."""
    wanted = [] if sandbox_usable(executable.parent) else [NO_SANDBOX]
    return [argument for argument in wanted if argument not in existing]


def environment(config: dict[str, Any]) -> dict[str, str]:
    """Which display backend Electron should ask Ozone for.

    Left to itself Electron picks Wayland whenever a Wayland session is present.
    On an NVIDIA setup that path cannot allocate scanout buffers: it fails with
    "Cannot create bo with format=RGBA_8888" and takes the GPU context down with
    it, so the window never appears or dies shortly after. XWayland has no such
    trouble, and enable_wayland is already how the native backend is asked for.
    """
    return {OZONE_HINT: "wayland" if config.get("enable_wayland") else "x11"}
