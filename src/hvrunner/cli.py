"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from .core import entries, installer
from .core.affinity import supervise
from .core.config import expand, load_config, save_config
from .core.constants import APP_NAME, config_path
from .core.launcher import launch, reap_children_automatically
from .core.library import library
from .core.logs import LogReader, recent_logs
from .core.models import HvrunnerError
from .tui import run_tui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="Terminal game library and Proton launcher")
    parser.add_argument("--list", action="store_true", help="print discovered games without opening the interface")
    parser.add_argument("--launch", metavar="NAME", help="launch the single game matching NAME")
    parser.add_argument("--init-config", action="store_true", help="write default configuration if it is absent")
    parser.add_argument("--logs", action="store_true", help="print the most recent launch log and exit")
    parser.add_argument("--affinity-watch", nargs=2, metavar=("EXE", "DIR"), help=argparse.SUPPRESS)
    parser.add_argument("--install", metavar="PATH", help="run a Windows installer into a new game folder")
    parser.add_argument("--name", metavar="NAME", help="name for the game created by --install")
    return parser


def _print_latest_log() -> int:
    logs = recent_logs(limit=1)
    if not logs:
        print(f"{APP_NAME}: no logs yet", file=sys.stderr)
        return 1
    reader = LogReader(logs[0])
    reader.poll()
    print(f"# {logs[0]}")
    for line in reader.lines:
        print(line)
    return 0


def _install(config: dict[str, Any], source_text: str, name: str | None) -> int:
    """Install headlessly, taking the top ranked binary rather than asking."""
    source = Path(expand(source_text))
    if not source.is_file() or source.suffix.lower() != ".exe":
        raise HvrunnerError(f"no readable .exe at {source}")
    roots = [Path(expand(str(root))) for root in config["library_roots"]]
    if not roots:
        raise HvrunnerError("no library folder is configured")
    chosen_name = name or source.stem
    target = installer.prepare_target(roots[0], chosen_name)
    run = installer.start(source, target, config)
    print(f"Installing {chosen_name}")
    print(f"Log: {run.log_path}")
    while installer.running(run):
        time.sleep(1.0)
    candidates = installer.discover(run.prefix, chosen_name)
    if not candidates:
        raise HvrunnerError(f"{chosen_name} installed, but no executable was found in {run.prefix}")
    entries.add(
        config,
        {
            "name": chosen_name,
            "executable": str(candidates[0]),
            "install_dir": str(target),
            "launch_args": [],
        },
    )
    save_config(config_path(), config)
    print(f"Added {chosen_name} -> {candidates[0]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.affinity_watch:
        supervise(args.affinity_watch[0], args.affinity_watch[1])
        return 0
    reap_children_automatically()
    path = config_path()
    try:
        config = load_config(path)
        if args.init_config:
            if path.exists():
                print(f"Configuration already exists: {path}")
            else:
                save_config(path, config)
                print(f"Created {path}")
            return 0
        if args.logs:
            return _print_latest_log()
        if args.install:
            return _install(config, args.install, args.name)
        games = library(config)
        if args.launch:
            query = args.launch.casefold()
            matches = [game for game in games if query in game.name.casefold()]
            if len(matches) != 1:
                raise HvrunnerError(f"--launch matched {len(matches)} games; use a more specific name")
            result = launch(matches[0], config)
            print(f"Launched {matches[0].name} (pid {result.pid})")
            print(f"Log: {result.log_path}")
            return 0
        if args.list:
            for game in games:
                star = "*" if game.favorite else " "
                print(f"{star}\t{game.source}\t{game.name}\t{game.executable}")
            return 0
        run_tui(config, path)
    except HvrunnerError as error:
        print(f"{APP_NAME}: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0
