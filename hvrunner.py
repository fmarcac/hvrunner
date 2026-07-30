#!/usr/bin/env python3
"""Entry point for running from a checkout, without installing the package.

Kept at the repository root because the affinity watcher re-executes this file
when hvrunner is not on PATH.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from hvrunner.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
