"""Command line entry point."""

from __future__ import annotations

import argparse
import sys

from .affinity import supervise
from .config import load_config, save_config
from .constants import APP_NAME, config_path
from .launcher import launch, reap_children_automatically
from .library import library
from .logs import LogReader, recent_logs
from .models import HvrunnerError
from .tui import run_tui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="Terminal game library and Proton launcher")
    parser.add_argument("--list", action="store_true", help="print discovered games without opening the interface")
    parser.add_argument("--launch", metavar="NAME", help="launch the single game matching NAME")
    parser.add_argument("--init-config", action="store_true", help="write default configuration if it is absent")
    parser.add_argument("--logs", action="store_true", help="print the most recent launch log and exit")
    parser.add_argument("--affinity-watch", nargs=2, metavar=("EXE", "DIR"), help=argparse.SUPPRESS)
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
