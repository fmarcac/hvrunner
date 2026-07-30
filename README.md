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
./bin/hvrunner
```

Put it on PATH:

```bash
ln -s "$PWD/bin/hvrunner" ~/.local/bin/hvrunner
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
| `mangohud_config` | `""` (unset) | value for `MANGOHUD_CONFIG`; empty leaves your MangoHud.conf alone |
| `shader_cache` | `true` | persistent vkd3d and DXVK pipeline cache |
| `native_scale` | `false` | drop the output to scale 1 while a game runs |
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
MANGOHUD_CONFIG=fps,frametime,present_mode hvrunner
```

`mangohud_config` is empty by default, and that matters: `MANGOHUD_CONFIG`
**replaces** `~/.config/MangoHud/MangoHud.conf` rather than merging with it, so
setting it discards your whole HUD layout. Leaving it unset lets MangoHud read
your own file. It also avoids the `full` preset, whose media player module logs
an error on every poll when no MPRIS player is running.

`shader_cache` sets `VKD3D_SHADER_CACHE_PATH` and `DXVK_STATE_CACHE_PATH` to a
directory inside the prefix. umu only sets `STEAM_COMPAT_SHADER_PATH`, which
vkd3d-proton does not read, so without this every launch recompiles pipelines and
stutters as new shaders appear.

`native_scale` drops the output to scale 1 for the duration of a game and
restores it afterwards. On a fractionally scaled output the compositor has to
rescale a fullscreen game every frame, which rules out direct scanout. It is off
by default because a mode change while a game holds the output can be disruptive.

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
./bin/check          # ruff format, ruff check, markdownlint, pytest
./bin/check --fix    # apply the formatters first
```

`bin/check` is what CI runs and what the pre-commit hook runs, so there is one
definition of green. Enable the hook with:

```bash
git config core.hooksPath githooks
```
