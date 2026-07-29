# hvrunner

Terminal launcher for standalone Windows games on Linux.

`hvrunner` scans custom library folders for Windows executables and launches a
selected game directly with the configured Proton build. It does not call game
folder scripts or start the Steam client.

## Run

```bash
hvrunner
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
`Proton-GE11-1-LinUwUx` runtime. Library folders, Proton path, and the Proton
compatibility path can be changed in Settings.
