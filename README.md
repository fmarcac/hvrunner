# hvrunner

Terminal launcher for standalone Windows games on Linux.

`hvrunner` scans custom library folders for Windows executables and launches a
selected game with the configured Proton build through `umu`. It does not call
game-folder scripts or start the Steam client.

`umu` supplies the Steam Linux Runtime container that Proton requires for
non-Steam games. On Arch Linux, install it with:

```bash
sudo pacman -S umu-launcher
```

MangoHud starts with the full metrics overlay for every game. Press Right Shift
and F12 to hide or show it.

hvrunner keeps every game thread available to all CPU cores while the game is
running. This prevents launchers and games from leaving restrictive affinity
masks in place.

## Run

```bash
hvrunner
hvrunner --launch Bfresynced
```

For a one-launch Black Flag DLSS and frame-generation indicator check:

```bash
ACBF_VERIFY_DLSS=1 hvrunner --launch Bfresynced
```

## Controls

- `Enter`: launch selected game
- `s`: settings
- `a`: add executable
- `f`: favorite or unfavorite
- `r`: rescan library
- `q`: quit

## Configuration

Configuration is saved to `~/.config/hvrunner/config.json` on the first change.
By default, hvrunner scans `/mnt/data/games` and uses the installed
`Proton-GE11-1-LinUwUx` runtime. Library folders, Proton path, and the `umu`
runner path can be changed in Settings.
