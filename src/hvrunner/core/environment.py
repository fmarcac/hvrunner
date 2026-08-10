"""The environment a game is launched with."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .constants import DEFAULT_WINEDEBUG
from .models import Game, HvrunnerError

# Environment names worth showing in the interface, in display order. Anything
# else hvrunner sets is either uninteresting or derivable from these.
NOTABLE_ENV = (
    "PROTONPATH",
    "WINEPREFIX",
    "VKD3D_SHADER_CACHE_PATH",
    "MANGOHUD_CONFIG",
    "PROTON_ENABLE_WAYLAND",
    "DXVK_ENABLE_NVAPI",
    "DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS",
    "NVPRESENT_ENABLE_SMOOTH_MOTION",
)

# Names belonging to the Windows side of the compatibility layer. The interface
# colours these differently.
WINDOWS_SIDE_ENV = frozenset(
    {
        "DXVK_ENABLE_NVAPI",
        "DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS",
        "NVPRESENT_ENABLE_SMOOTH_MOTION",
        "WINEPREFIX",
        "WINEDEBUG",
    }
)


def _mkdir(path: Path, label: str) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise HvrunnerError(f"cannot create {label} {path}: {error}") from error


def game_environment(executable: Path, install_dir: str, prepare: bool) -> dict[str, str]:
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
            _mkdir(log_path, "log directory")
        environment.update(
            {
                "DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS": "DLSSIndicator=1024,DLSSGIndicator=2",
                "DXVK_NVAPI_LOG_LEVEL": "info",
                "DXVK_NVAPI_LOG_PATH": str(log_path),
            }
        )
    return environment


def _overlay(environment: dict[str, str], config: dict[str, Any]) -> None:
    """MangoHud, Wayland and user supplied entries."""
    # Popped rather than merely left unset when off: the environment is
    # inherited, so MANGOHUD=1 in the shell that started hvrunner would
    # otherwise turn the overlay back on for a launch that asked for no overlay.
    if config.get("use_mangohud", True):
        environment["MANGOHUD"] = "1"
        # Only set MANGOHUD_CONFIG when there is something to say. It replaces
        # the user's MangoHud.conf rather than merging, so an unnecessary value
        # would silently discard their HUD layout.
        mangohud_config = os.environ.get("MANGOHUD_CONFIG") or str(config.get("mangohud_config") or "")
        if mangohud_config:
            environment["MANGOHUD_CONFIG"] = mangohud_config
    else:
        environment.pop("MANGOHUD", None)
        environment.pop("MANGOHUD_CONFIG", None)

    if config.get("enable_wayland"):
        environment["PROTON_ENABLE_WAYLAND"] = "1"
    else:
        environment.pop("PROTON_ENABLE_WAYLAND", None)

    extra_env = config.get("extra_env") or {}
    if isinstance(extra_env, dict):
        for name, value in extra_env.items():
            environment[str(name)] = str(value)


def build(game: Game, config: dict[str, Any], proton: Path, prefix: Path, *, prepare: bool) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "GAMEID": "0",
            "PROTONPATH": str(proton),
            "WINEPREFIX": str(prefix),
            "WINEDEBUG": DEFAULT_WINEDEBUG,
            "PROTON_USE_XALIA": "0",
            "DISABLE_GAMESCOPE_WSI": "1",
        }
    )

    if config.get("shader_cache", True):
        cache = prefix / "shadercache"
        if prepare:
            _mkdir(cache, "shader cache")
        # vkd3d-proton reads VKD3D_SHADER_CACHE_PATH; DXVK reads its own. umu
        # sets neither, only STEAM_COMPAT_SHADER_PATH.
        environment["VKD3D_SHADER_CACHE_PATH"] = str(cache)
        environment["DXVK_STATE_CACHE_PATH"] = str(cache)

    environment.update(game_environment(Path(game.executable), game.install_dir, prepare))
    _overlay(environment, config)
    return environment
