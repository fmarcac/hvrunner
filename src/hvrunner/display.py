"""Reading and changing output scale through hyprctl.

A fractionally scaled output forces the compositor to rescale a fullscreen game
every frame, which rules out direct scanout and caps throughput well below what
the GPU can do. Setting the output to scale 1 for the duration of a game removes
that copy.

Every function degrades to a no-op when hyprctl is missing, so nothing here is
required for hvrunner to work.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass

TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class Monitor:
    name: str
    width: int
    height: int
    refresh: float
    x: int
    y: int
    scale: float

    def spec(self, scale: float) -> str:
        """A monitor argument in the form hyprctl keyword expects."""
        return f"{self.name},{self.width}x{self.height}@{self.refresh:.3f},{self.x}x{self.y},{scale:g}"

    @property
    def scaled(self) -> bool:
        return abs(self.scale - 1.0) > 0.001


def available() -> bool:
    return shutil.which("hyprctl") is not None


def parse_monitors(payload: str) -> list[Monitor]:
    try:
        entries = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(entries, list):
        return []
    monitors: list[Monitor] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            monitors.append(
                Monitor(
                    name=str(entry["name"]),
                    width=int(entry["width"]),
                    height=int(entry["height"]),
                    refresh=float(entry["refreshRate"]),
                    x=int(entry.get("x", 0)),
                    y=int(entry.get("y", 0)),
                    scale=float(entry.get("scale", 1.0)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return monitors


def _run(arguments: list[str]) -> str | None:
    if not available():
        return None
    try:
        finished = subprocess.run(
            ["hyprctl", *arguments],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if finished.returncode != 0:
        return None
    return finished.stdout


def monitors() -> list[Monitor]:
    payload = _run(["-j", "monitors"])
    return parse_monitors(payload) if payload else []


def focused_monitor() -> Monitor | None:
    payload = _run(["-j", "monitors"])
    if not payload:
        return None
    try:
        entries = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(entries, list):
        return None
    chosen = next((e for e in entries if isinstance(e, dict) and e.get("focused")), None)
    found = parse_monitors(json.dumps([chosen] if chosen else entries))
    return found[0] if found else None


def apply(spec: str) -> bool:
    """Set a monitor. Runtime only, so nothing is written to the Hyprland config."""
    return _run(["keyword", "monitor", spec]) is not None
