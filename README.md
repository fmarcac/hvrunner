# hvrunner

Terminal launcher for standalone Windows games on Linux.

hvrunner scans library folders for Windows executables and launches the selected
game with the configured Proton build through `umu`, wrapped in MangoHud and
optionally gamemode. It does not call game-folder scripts and it does not start
the Steam client.

`umu` supplies the Steam Linux Runtime container that Proton needs for non-Steam
games. On Arch Linux:

```bash
sudo pacman -S umu-launcher
```

Standard library only, no Python runtime dependencies.

## Install

Run from a checkout:

```bash
./hvrunner.py
```

Put it on PATH:

```bash
ln -s "$PWD/run.sh" ~/.local/bin/hvrunner
```

Or install the package, which provides the same command:

```bash
pip install -e .
```

## Run

```bash
hvrunner                  # library browser
hvrunner --list           # print discovered games
hvrunner --launch NAME    # launch the one game matching NAME
hvrunner --logs           # print the most recent launch log
hvrunner --init-config    # write the default configuration
```

For a one-launch Black Flag DLSS and frame-generation indicator check:

```bash
ACBF_VERIFY_DLSS=1 hvrunner --launch bfresynced
```

## Controls

| Key | Action |
| --- | --- |
| `enter` | launch the selected game |
| `j` / `k` | move down and up |
| `f` | toggle favourite, favourites sort first |
| `a` | add an executable by path |
| `r` | rescan library folders |
| `l` | open the log feed |
| `s` | settings |
| `?` | key reference |
| `q` | quit |

In the log feed: `j`/`k` scroll, `PgUp`/`PgDn` by a screen, `g`/`G` jump to the
ends, `f` toggles following new output, `n`/`p` switch between logs.

## Game output

Everything a game and its helpers print goes to
`~/.local/state/hvrunner/logs/<timestamp>-<game>.log`, and the log feed reads it
back. Sending that output to the terminal directly interleaves it with the
interface and produces half overwritten lines, so it is captured instead. Escape
sequences and carriage-return progress lines are cleaned on the way in. The
twenty most recent logs are kept.

## Configuration

`~/.config/hvrunner/config.json`, created by `--init-config` or on the first
change made in the interface.

| Key | Default | Meaning |
| --- | --- | --- |
| `library_roots` | `["/mnt/data/games"]` | folders whose subdirectories are scanned |
| `proton_path` | Proton GE in the Steam compat dir | Proton build to run |
| `umu_path` | `/usr/bin/umu-run` | umu launcher |
| `custom_prefix_name` | `.hvrunner-proton` | prefix folder, created inside the game folder |
| `enforce_all_cpus` | `true` | keep game threads spread across every CPU |
| `mangohud_config` | `toggle_hud=Shift_R+F12` | value for `MANGOHUD_CONFIG` |
| `use_gamemode` | `true` | wrap the command in `gamemoderun` |
| `enable_wayland` | `false` | set `PROTON_ENABLE_WAYLAND`, bypassing XWayland |
| `extra_env` | `{}` | extra environment, applied last |
| `favorites` | `[]` | favourite keys, managed by the interface |
| `custom_games` | `[]` | executables added by hand |

A wrong type is rejected with a message naming the key, rather than failing
somewhere distant.

A `MANGOHUD_CONFIG` already in the environment takes precedence over
`mangohud_config`, so a single run can be changed without editing the file:

```bash
MANGOHUD_CONFIG=vulkan_present_mode=mailbox,present_mode hvrunner
```

`mangohud_config` deliberately avoids the `full` preset. `full` enables the
media player module, which logs an error on every poll when no MPRIS player is
running. Put display options in `~/.config/MangoHud/MangoHud.conf` instead.

Affinity enforcement keeps every game thread available to all CPUs while the
game runs, so launchers and games cannot leave a restrictive mask in place.

## Executable selection

For each subdirectory of a library root, hvrunner looks for `.exe` files up to
three levels deep, skipping hidden directories so the Proton prefix inside the
game folder is ignored. Installer-looking names are filtered out. The rest are
ranked by depth, then by how closely the name matches the folder, then
alphabetically. File size is not a tiebreak, because ranking by size can
silently switch to a larger sibling binary such as a `_Plus` variant.

## Development

```bash
ruff check src tests
python -m pytest
```
