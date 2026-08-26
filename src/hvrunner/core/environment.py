"""The environment a game is launched with."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import electron
from .constants import DEFAULT_COMPAT_ROOT, DEFAULT_WINEDEBUG, SPACEWAR_APPID
from .models import Game, HvrunnerError

# Environment names worth showing in the interface, in display order. Anything
# else hvrunner sets is either uninteresting or derivable from these.
NOTABLE_ENV = (
    "PROTONPATH",
    "WINEPREFIX",
    "SteamAppId",
    "STEAM_COMPAT_CLIENT_INSTALL_PATH",
    "PROTON_DISABLE_LSTEAMCLIENT",
    "VKD3D_SHADER_CACHE_PATH",
    "MANGOHUD_CONFIG",
    "PROTON_ENABLE_WAYLAND",
    electron.OZONE_HINT,
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


def steam_root(config: dict[str, Any]) -> Path:
    return Path(str(config.get("steam_root") or DEFAULT_COMPAT_ROOT)).expanduser()


# Where a repack keeps the application id it expects to run as. Only fixed
# shapes, no walk: plan() runs on every cursor move to draw the preview.
APPID_FILES = (
    "steam_appid.txt",
    # Goldberg's own layout, which is not under a Unity _Data folder. A repack
    # built around ColdClientLoader keeps its id here and nowhere else.
    "steam_settings/steam_appid.txt",
    "*_Data/Plugins/x86_64/steam_settings/steam_appid.txt",
    "*_Data/Plugins/x86_64/steam_appid.txt",
    "*_Data/Plugins/steam_settings/steam_appid.txt",
)


# A bundled fix presents one id to Steam while telling the game it is another.
# OnlineFix and FreeTP's SteamFix spell it FakeAppId, unsteam fake_app_id; all
# three mean the same thing, and it is the one that has to reach the
# environment. Reading the real id instead is how Approximately Up got 3904850
# when its fix expected 480.
#
# SteamFix.ini sits beside RealAppId in the same file, so the key matters more
# than the filename: taking the first number in the file would give the id the
# game believes it has rather than the one Steam has to be shown.
FIX_FILES = ("OnlineFix.ini", "SteamFix.ini", "unsteam.ini")
FIX_KEY = "fakeappid"


def _digits(text: str) -> str:
    return "".join(character for character in text if character.isdigit())


def fix_appid(executable: Path) -> str:
    """The id a bundled fix wants presented to Steam, if one is installed."""
    for name in FIX_FILES:
        path = executable.parent / name
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            key, separator, value = line.partition("=")
            if not separator:
                continue
            if key.strip().replace("_", "").casefold() == FIX_KEY:
                found = _digits(value)
                if found:
                    return found
    return ""


def settings_appid(executable: Path) -> str:
    """The application id the game itself declares, if it declares one."""
    folder = executable.parent
    for pattern in APPID_FILES:
        try:
            found = sorted(folder.glob(pattern))
        except OSError:
            continue
        for path in found:
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue
            digits = _digits(text)
            if digits:
                return digits
    return ""


def application_id(game: Game) -> str:
    """The Steam application a game runs as.

    A declared id wins, then a bundled fix's fake id, then whatever the game
    ships, then Spacewar.

    The fix comes before the game's own settings because it exists to present a
    different id than the game believes it has: reading the game's instead gave
    Approximately Up 3904850 when its OnlineFix expected 480.

    The game's own id comes before Spacewar because a repack with a bundled
    emulator reads its steam_settings and ignores the environment. Forcing
    Spacewar put the two in contradiction and the game exited before its engine
    started, with nothing in the log to say why.

    The fallback must never be empty. protonfixes derives its own game id from
    the digits in STEAM_COMPAT_DATA_PATH and raises IndexError when the path
    holds none, which a prefix named .hvrunner-proton always does, so an unset
    id kills the launch outright.
    """
    executable = Path(game.executable)
    return game.steam_appid or fix_appid(executable) or settings_appid(executable) or SPACEWAR_APPID


def game_environment(executable: Path, install_dir: str, prepare: bool) -> dict[str, str]:
    """Per title workarounds, keyed off the executable name.

    This is not where a new workaround belongs. An entry carries its own env,
    which is applied after this and wins over it, so a game needing one is a
    change to the library rather than to the package. What is left here is the
    measured Black Flag setup, kept because it is relied on and tested.
    """
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
    appid = application_id(game)
    environment = os.environ.copy()
    environment.update(
        {
            "PROTONPATH": str(proton),
            "WINEPREFIX": str(prefix),
            "WINEDEBUG": DEFAULT_WINEDEBUG,
            "PROTON_USE_XALIA": "0",
            "DISABLE_GAMESCOPE_WSI": "1",
            # The name umu could never pass on. Without it Proton's
            # setup_steam_files leaves C:\\Program Files (x86)\\Steam empty
            # while still writing SteamPath into the registry, and anything
            # resolving a Steam file through that key loads nothing.
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam_root(config)),
            # Proton derives WINEPREFIX from this, as <path>/pfx, which is why
            # the prefix carries a pfx symlink pointing back at itself.
            "STEAM_COMPAT_DATA_PATH": str(prefix),
            "STEAM_COMPAT_APP_ID": appid,
            "SteamAppId": appid,
            "SteamGameId": appid,
            "SteamEnv": "1",
            # Proton-GE turns the bridge off itself unless this name is already
            # in the environment, whatever its value.
            "PROTON_DISABLE_LSTEAMCLIENT": "0",
        }
    )
    # umu's own spelling of the application id, and the source of the umu-<id>
    # regex trap. Nothing reads it now, and an inherited one would only mislead.
    environment.pop("GAMEID", None)

    if config.get("shader_cache", True):
        cache = prefix / "shadercache"
        if prepare:
            _mkdir(cache, "shader cache")
        # vkd3d-proton reads VKD3D_SHADER_CACHE_PATH; DXVK reads its own.
        environment["VKD3D_SHADER_CACHE_PATH"] = str(cache)
        environment["DXVK_STATE_CACHE_PATH"] = str(cache)

    environment.update(game_environment(Path(game.executable), game.install_dir, prepare))
    _overlay(environment, config)
    # Last, so the entry's own environment wins over the global extra_env and
    # over every default above. This is what keeps a new game needing a DXVK or
    # NVAPI workaround from meaning a change to this file.
    environment.update(game.env)
    return environment


def native(game: Game, config: dict[str, Any]) -> dict[str, str]:
    """The environment a native Linux game is launched with.

    None of the STEAM_COMPAT names, no prefix and no WINEDEBUG, because there is
    no Wine in this launch. The overlay and the user's own entries still apply:
    those are about the machine rather than the compatibility layer.
    """
    environment = os.environ.copy()
    executable = Path(game.executable)
    if electron.is_electron(executable):
        environment.update(electron.environment(config))
    _overlay(environment, config)
    environment.update(game.env)
    return environment
