# hvrunner

Terminal launcher for standalone Windows games on Linux.

hvrunner scans library folders for games and launches the selected one wrapped
in MangoHud and optionally gamemode. A Windows program goes through the
configured Proton build; a native Linux build is started directly, with no
prefix. It does not call game-folder scripts and it does not start the Steam
client.

Proton is invoked directly rather than through `umu`. umu assigns
`STEAM_COMPAT_CLIENT_INSTALL_PATH` an empty string and never reassigns it, so
Proton left `C:\Program Files (x86)\Steam` empty in every prefix while still
writing `SteamPath` into the registry. Anything that resolved a Steam file
through that key loaded nothing: a genuine `steam_api64.dll` reported Steam as
not running, and OnlineFix's `SteamOverlay64.dll` failed
`GameOverlayRenderer64.dll` with error 126. Running Proton directly passes the
real path, populates the prefix, and still applies protonfixes.

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
hvrunner                          # library browser
hvrunner --list                   # print discovered games
hvrunner --launch NAME            # launch the one game matching NAME
hvrunner --logs                   # print the most recent launch log
hvrunner --init-config            # write the default configuration
hvrunner --install PATH           # run a Windows installer (.exe or .msi) into a new game folder
hvrunner --install PATH --name NAME   # name the game created by --install
```

For a one-launch Black Flag DLSS and frame-generation indicator check:

```bash
ACBF_VERIFY_DLSS=1 hvrunner --launch bfresynced
```

## Controls

| Key       | Action                                                   |
| --------- | -------------------------------------------------------- |
| `enter`   | launch the selected game                                 |
| `S`       | launch the selected game as Spacewar, Steam app id 480   |
| `j` / `k` | move down and up                                         |
| `f`       | toggle favourite, favourites sort first                  |
| `e`       | edit, rename or delete the selected game                 |
| `a`       | add an executable, Windows or native, by path or browser |
| `i`       | install from a Windows installer                         |
| `r`       | rescan library folders                                   |
| `l`       | open the log feed                                        |
| `s`       | settings                                                 |
| `?`       | key reference                                            |
| `q`       | quit                                                     |

In the log feed: `j`/`k` scroll, `PgUp`/`PgDn` by a screen, `g`/`G` jump to the
ends, `f` toggles following new output, `n`/`p` switch between logs.

`S` runs the game under Steam application id 480, Spacewar, and turns on
Proton's `lsteamclient` bridge, which this Proton build disables by default. It
is what a game expecting a real `SteamAppId` wants. It does not give you the
Steam overlay or Steam Input: both need the game launched by Steam itself, as a
non-Steam shortcut. A game shipping its own Steam emulator keeps using that
instead. To make it stick for one game, set its Steam app id in the entry editor
with `e`; `S` stays a one off that ignores whatever is stored.

Anywhere a path is asked for, the field takes a value of any length and scrolls
sideways: arrow keys and `^a`/`^e` move, `^w` rubs out one folder, `^u` clears.
`tab` opens a file browser starting from the deepest part of what you have
typed, or from your library folder when it is empty. In the browser `j`/`k`
move, `enter` opens a folder or picks a file, `h` or `backspace` goes up, `s`
takes the current folder when a folder is what is wanted, and `esc` returns to
the field with what you typed still there.

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

| Key                  | Default                           | Meaning                                                                                                                                                  |
| -------------------- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `library_roots`      | `["/mnt/data/games"]`             | folders whose subdirectories are scanned                                                                                                                 |
| `proton_path`        | Proton GE in the Steam compat dir | Proton build to run                                                                                                                                      |
| `steam_root`         | `~/.local/share/Steam`            | Steam install Proton copies `steamclient64.dll` and the overlay from                                                                                     |
| `custom_prefix_name` | `.hvrunner-proton`                | prefix folder, created inside the game folder                                                                                                            |
| `enforce_all_cpus`   | `true`                            | keep game threads spread across every CPU                                                                                                                |
| `mangohud_config`    | `""` (unset)                      | value for `MANGOHUD_CONFIG`; empty leaves your MangoHud.conf alone                                                                                       |
| `shader_cache`       | `true`                            | persistent vkd3d and DXVK pipeline cache                                                                                                                 |
| `native_scale`       | `false`                           | drop the output to scale 1 while a game runs                                                                                                             |
| `use_gamemode`       | `true`                            | wrap the command in `gamemoderun`                                                                                                                        |
| `use_mangohud`       | `true`                            | wrap the command in `mangohud` and set `MANGOHUD=1`                                                                                                      |
| `enable_wayland`     | `false`                           | set `PROTON_ENABLE_WAYLAND`, bypassing XWayland                                                                                                          |
| `extra_env`          | `{}`                              | extra environment, applied last                                                                                                                          |
| `favorites`          | `[]`                              | favourite keys, managed by the interface                                                                                                                 |
| `custom_games`       | `[]`                              | executables added, installed or edited by hand, each with an `install_dir` naming where its Proton prefix lives, and an optional `env` object of its own |

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

An entry's own `env` is applied after everything else, so it wins over
`extra_env` and over every default hvrunner sets. That is where a DXVK or NVAPI
workaround for one title belongs, and the entry editor has a field for it:

```json
{
  "name": "Some Game",
  "executable": "/mnt/data/games/Some Game/Game.exe",
  "install_dir": "/mnt/data/games/Some Game",
  "env": { "DXVK_ENABLE_NVAPI": "1" }
}
```

`shader_cache` sets `VKD3D_SHADER_CACHE_PATH` and `DXVK_STATE_CACHE_PATH` to a
directory inside the prefix. `STEAM_COMPAT_SHADER_PATH` alone is not enough,
because vkd3d-proton does not read it, so without this every launch recompiles
pipelines and stutters as new shaders appear.

`native_scale` drops the output to scale 1 for the duration of a game and
restores it afterwards. On a fractionally scaled output the compositor has to
rescale a fullscreen game every frame, which rules out direct scanout. It is off
by default because a mode change while a game holds the output can be
disruptive.

Affinity enforcement keeps every game thread available to all CPUs while the
game runs, so launchers and games cannot leave a restrictive mask in place.

## What it can launch

| Kind             | How it is started                                 |
| ---------------- | ------------------------------------------------- |
| `.exe`           | `proton run <path>`                               |
| `.bat` or `.cmd` | `proton run cmd /c <name>`                        |
| `.msi`           | `proton run msiexec /i <name>`                    |
| anything else    | directly, if it has the executable bit; no Proton |

A native Linux build gets the wrappers and your own environment but no prefix,
no `WINEDEBUG` and none of the `STEAM_COMPAT` names, because there is no Wine in
that launch. `cmd` and `msiexec` are given a bare filename rather than a path,
because neither takes a unix path for what it is opening and the game is already
started in its own folder.

## Executable selection

For each subdirectory of a library root, hvrunner looks for Windows programs up
to four levels deep, skipping hidden directories so the Proton prefix inside the
game folder is ignored. A folder holding none is looked at again, two levels
deep, for a file with the executable bit: that is a native build's launcher,
which has no extension to recognise it by.

Installer-looking names are filtered out, unless filtering would leave nothing.
The rest are ranked by depth, then by how closely the name matches the folder,
then by kind, then alphabetically. File size is not a tiebreak, because ranking
by size can silently switch to a larger sibling binary such as a `_Plus`
variant.

The scan reads directory entries without stat'ing them, so a full library scan
is a few milliseconds and rescanning is cheap. Toggling a favourite does not
rescan at all; it re-sorts what is already in memory.

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
