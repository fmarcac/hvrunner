"""Configuration loading, validation and atomic saving."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .constants import (
    DEFAULT_CUSTOM_ROOT,
    DEFAULT_MANGOHUD_CONFIG,
    DEFAULT_PROTON,
    DEFAULT_UMU,
)
from .models import HvrunnerError


def default_config() -> dict[str, Any]:
    return {
        "library_roots": [str(DEFAULT_CUSTOM_ROOT)],
        "proton_path": str(DEFAULT_PROTON),
        "umu_path": str(DEFAULT_UMU),
        "custom_prefix_name": ".hvrunner-proton",
        "enforce_all_cpus": True,
        # MANGOHUD_CONFIG already present in the environment wins over this, so a
        # one-off override needs no config edit.
        "mangohud_config": DEFAULT_MANGOHUD_CONFIG,
        # gamemoderun wraps the command. Turning this off silences the
        # "libgamemode.so: cannot open shared object file" noise from 32-bit and
        # in-container helpers, at the cost of gamemode's scheduling tweaks.
        "use_gamemode": True,
        # Proton's native Wayland backend, rather than presenting through
        # XWayland. Off keeps the historical behaviour.
        "enable_wayland": False,
        # Applied last, so it wins over everything hvrunner sets.
        "extra_env": {},
        "favorites": [],
        "custom_games": [],
    }


_TYPE_NAMES: dict[type, str] = {bool: "a boolean", list: "a list", dict: "an object", str: "a string"}


def _validate_type(key: str, value: Any, default: Any, path: Path) -> Any:
    """Reject a value whose type would only fail much later.

    A string where a list belongs is the dangerous case: iterating it yields
    characters, and every character would be treated as a library root.
    """
    # bool must be checked before int-like types; bool is a subclass of int.
    for expected_type, description in _TYPE_NAMES.items():
        if isinstance(default, expected_type):
            if not isinstance(value, expected_type):
                raise HvrunnerError(f"cannot read {path}: {key!r} must be {description}")
            return value
    return value


def load_config(path: Path) -> dict[str, Any]:
    config = default_config()
    if not path.exists():
        return config
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise HvrunnerError(f"cannot read {path}: {error}") from error
    if not isinstance(data, dict):
        raise HvrunnerError(f"cannot read {path}: top level must be an object")
    for key, value in data.items():
        if key in config:
            config[key] = _validate_type(key, value, config[key], path)
    return config


def save_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # with_name, not with_suffix: a filename containing dots must not have part
    # of its name eaten to build the temporary path.
    temporary = path.with_name(path.name + ".tmp")
    payload = json.dumps(config, indent=2, sort_keys=True) + "\n"
    try:
        with temporary.open("w") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise HvrunnerError(f"cannot write {path}: {error}") from error


def expand(value: str) -> str:
    """Normalise a user-entered path once, in one place."""
    return str(Path(value).expanduser())
